#!/usr/bin/env python
# token_stream.py - parse a stream of PDF spec tokens from a stream of bytes

import os
import re
import sys
from enum import Enum, auto, unique
from byte_stream import ByteStream

bEOLSP = b'(\r\n| \r| \n)'

#-------------------------------------------------------------------------------
# I want stdout to be unbuffered, always
#-------------------------------------------------------------------------------

class Unbuffered(object):
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

import sys
sys.stdout = Unbuffered(sys.stdout)

#-------------------------------------------------------------------------------
#  EToken
#-------------------------------------------------------------------------------

# Possible token types in PDF files
@unique
class EToken(Enum):
    ERROR = auto()             # pseudo-token describing a parsing error 
    EOF = auto()               # pseudo-token describing the EOF condition
    VERSION_MARKER = auto()    # %PDF-n.m
    EOF_MARKER = auto()        # %%EOF
    INTEGER = auto()
    REAL = auto()
    # I'm not sure I need to distinguish the next 2 tokens. Maybe just knowing
    # that it's a string will turn out to be enough.
    LITERAL_STRING = auto()    # (xxxxx) FIXME maybe a single STRING token ?
    HEX_STRING = auto()        # <xxxxx>
    NAME = auto()              # /xxxxx
    ARRAY_BEGIN = auto()       # '['
    ARRAY_END = auto()         # ']'
    DICT_BEGIN = auto()        # '<<'
    DICT_END = auto()          # '>>'
    TRUE = auto()              # true
    FALSE = auto()             # false
    NULL = auto()              # null
    OBJECT_BEGIN = auto()      # obj
    OBJECT_END = auto()        # endobj
    STREAM_BEGIN = auto()      # stream
    STREAM_END = auto()        # endstream
    OBJ_REF = auto()           # 'R'
    XREF_SECTION = auto()      # xref
    TRAILER = auto()           # trailer
    STARTXREF = auto()         # startxref
    CR = auto()                # carriage return, \r, 0d
    LF = auto()                # newline, \n, 0a
    CRLF = auto()              # \r\n, 0d0a
    SUBSECTION_HDR = auto()    # xref sub-section header
    SUBSECTION_ENTRY = auto()  # xref sub-section entry
    UNEXPECTED = auto()        # asked for a header, got something else

    def __str__(self):
        """Print out 'NAME' instead of 'EToken.NAME'."""
        return self.name

#-------------------------------------------------------------------------------
# class Token
#-------------------------------------------------------------------------------

class Token():
    """Tokens are parsed from the input character stream.
Tokens are separated from each other by whitespace and/or delimiter characters.
"""
    def __init__(self, type, data=None):
        self.type = type
        self.data = data

    def __str__(self):
        s = f'{self.type}('
        if self.type == EToken.VERSION_MARKER:
            (major, minor) = self.data
            s += f'{major}, {minor}'
        elif self.type == EToken.INTEGER or self.type == EToken.REAL:
            s += str(self.data)
        elif self.type == EToken.LITERAL_STRING or self.type == EToken.HEX_STRING:
            s += self.data[:len(self.data)].decode('unicode_escape')
        elif self.type == EToken.NAME:
            # FIXME non ascii bytes may be found in here
            s += self.data.decode()
        elif self.type == EToken.ERROR:
            s += self.data
        s += ')'
        return s

    def begin(self):
        return self.type in [EToken.ARRAY_BEGIN, EToken.DICT_BEGIN, EToken.OBJECT_BEGIN]

    def end(self):
        return self.type in [EToken.ARRAY_END, EToken.DICT_END, EToken.OBJECT_END]
        
    def print_indented(self, indent):
        print(' '*4*indent + self.__str__())
        
#-------------------------------------------------------------------------------
# class TokenStream
#-------------------------------------------------------------------------------

class TokenStream:
    # Character classes
    wspace = b'\0\t\f '
    # wspace = b'\0\t\n\r\f '
    delims = b'()<>[]{}/%'
    hex_digit = b'0123456789abcdefABCDEF'

    # Initializer
    def __init__(self, filepath, f):
        self.bf = ByteStream(filepath, f)
        self.f = f
        self.cc = self.bf.next_byte()
        self.parens = 0
        self.peeked = []

    def seek(self, offset):
        self.bf.seek(offset)
        # Normal init
        self.cc = self.bf.next_byte()
        self.parens = 0
        self.peeked = []
        
    #---------------------------------------------------------------------------
    # get_literal_string
    #---------------------------------------------------------------------------

    def get_literal_string(self):
        """Found the opening paren, now get the entire string."""
        # The opening parens did not go into ls. We have not yet read the
        # first character of the literal.
        ls = bytearray()
        while True:
            cc = self.bf.next_byte()
            if cc == ord(')'):
                self.parens -= 1
                if self.parens == 0:
                    # stack is empty, this was the closing parenthesis
                    # (it does not go into ls)
                    return ls
                else:
                    ls.append(cc)
            elif cc == ord('('):
                self.parens += 1
                ls.append(cc)
            elif cc == ord('\\'):
                # Escape sequences
                pos = self.bf.tell()
                cc2 = self.bf.next_byte()
                if cc2 == ord('n'):
                    ls.append(ord('\n'))
                    self.bf.next_byte()
                elif cc2 == ord('r'):
                    ls.append(ord('\r'))
                    self.bf.next_byte()
                elif cc2 == ord('t'):
                    ls.append(ord('\t'))
                    self.bf.next_byte()
                elif cc2 == ord('b'):
                    ls.append(ord('\b'))
                    self.bf.next_byte()
                elif cc2 == ord('f'):
                    ls.append(ord('\f'))
                    self.bf.next_byte()
                elif cc2 == ord('('):
                    ls.append(ord('('))
                    self.bf.next_byte()
                elif cc2 == ord(')'):
                    ls.append(ord(')'))
                    self.bf.next_byte()
                elif cc2 == ord('\\'):
                    ls.append(ord('\\'))
                    self.bf.next_byte()
                else:
                    # next_byte may fail if there are less than 3 characters in
                    # the stream. In that case, the backslash should be
                    # ignored, and the following character(s) read.
                    self.bf.seek(pos)
                    s = self.bf.next_byte(3)
                    try:
                        c = int(s, 8)
                        ls.append(c)
                        self.bf.next_byte(3)
                    except ValueError as e:
                        # Backslash was not followed by one of the expected
                        # characters, just ignore it. The character following
                        # the backslash wasn't read.
                        # FIXME this error case is not handled
                        print(error)
            else:
                # All other characters just get added to the string
                ls.append(cc)

    #---------------------------------------------------------------------------
    # get_hex_string
    #---------------------------------------------------------------------------

    def get_hex_string(self):
        """Found the opening 'less than', now get the entire string.

        This actually returns a bytes object, since the hex digits can represent
        any value between 0 and 255, it's not necessarily ascii.
"""
        
        # The opening 'less than' did not go into the hex string 'hs'. We have
        # not yet read the first character of the hex literal.
        hs = bytearray()
        while True:
            cc = self.bf.next_byte()
            if cc == ord('>'):
                if len(hs)%2 == 1:
                    hs.append(ord('0'))
                # Each byte represents a hexadecimal digit, coded in ascii. If
                # I decode it, the resulting string will be suitable for fromhex())
                return bytes.fromhex(hs.decode())
            elif cc in TokenStream.hex_digit:
                hs.append(cc)
            else:
                # Incorrect value
                return None

    #---------------------------------------------------------------------------
    # get_name
    #---------------------------------------------------------------------------

    def get_name(self):
        """Found the opening '/', now get the rest of the characters."""
        # cc is the '/'. We have not yet read the first character of the
        # name. When this function returns, self.cc holds the next character to
        # be analyzed.
        name = bytearray()
        while True:
            cc = self.bf.next_byte()
            if cc in TokenStream.delims or cc in TokenStream.wspace or cc in b'\r\n':
                break
            if cc == ord('#'):
                # FIXME there may not be 2 characters left to read
                # FIXME handle error case when hc has invalid characters
                pos = self.bf.tell()  # useless ?
                s = self.bf.next_byte(2)
                if s[0] in TokenStream.hex_digit and s[1] in TokenStream.hex_digit:
                    name += bytes.fromhex(s.decode())
                else:
                    print('error')
                continue
            if cc < 33 or cc > 126:
                # Cf. PDF Spec 1.7 page 17
                print('error: character should be written using its 2-digit'
                      + ' hexadecimal code, preceded by the NUMBER SIGN only.')
                return None
            name.append(cc)

        # Don't move cc forward here. We've stopped on a delim or wspace, this
        # should be analyzed by the next handler. 
        self.cc = cc
        return name
      
    #---------------------------------------------------------------------------
    # get_regular_run
    #---------------------------------------------------------------------------

    def get_regular_run(self):
        """cc is a regular character, get the entire run of them."""
        # self.cc was analyzed by every handler in next_token, and not
        # recognized, so it's a regular character, and we want to accumulate
        # the entire consecutive run of regular characters.
        cc = self.cc
        
        s = bytearray()
        while (cc not in TokenStream.delims and cc not in TokenStream.wspace and
                   cc not in b'\r\n'):
            s.append(cc)
            cc = self.bf.next_byte()
        # cc now holds the first character not in 's', still to be analyzed

        if s == b'true':
            t = Token(EToken.TRUE)
        elif s == b'false':
            t = Token(EToken.FALSE)
        elif s == b'null':
            t = Token(EToken.NULL)
        elif s == b'obj':
            t = Token(EToken.OBJECT_BEGIN)
        elif s == b'endobj':
            t = Token(EToken.OBJECT_END)
        elif s == b'stream':
            t = Token(EToken.STREAM_BEGIN)
            # PDF Spec, § 7.3.8.1, page 19 :"The keyword stream that follows
            # the stream dictionary shall be followed by an end-of-line marker
            # consisting of either a CARRIAGE RETURN and a LINE FEED or just a
            # LINE FEED, and not by a CARRIAGE RETURN alone."
        elif s == b'endstream':
            t = Token(EToken.STREAM_END)
        elif s == b'R':
            t = Token(EToken.OBJ_REF)
        elif s == b'xref':
            t = Token(EToken.XREF_SECTION)
        elif s == b'trailer':
            t = Token(EToken.TRAILER)
        elif s == b'startxref':
            t = Token(EToken.STARTXREF)
        else:
            try:
                t = Token(EToken.INTEGER, int(s))
            except ValueError:
                try:
                    t = Token(EToken.REAL, float(s))
                except ValueError:
                    # cc has been read from the stream, but not yet
                    # analyzed. It is stored (persisted in between calls) in
                    # self.cc
                    self.cc = cc
                    return Token(EToken.ERROR,
                                 "Unrecognized regular character run.")
                
        # cc has been read from the stream, but not yet analyzed. It is stored
        # (persisted in between calls) in self.cc
        self.cc = cc
        return t
      
    #---------------------------------------------------------------------------
    # _next_token
    #---------------------------------------------------------------------------
 
    def _next_token(self):
        """Get and return the next token from the input stream."""
        # Invariant: cc has been read from the stream, but not yet analyzed. It
        # is stored (persisted in between calls) in self.cc. This means that
        # every time control leaves this function (through return), it must
        # read, but not analyze, the next character, and store it in self.cc.
        cc = self.cc

        # Have we reached EOF ?
        if cc == -1:
            return Token(EToken.EOF)

        # Start analyzing 
        while cc in TokenStream.wspace:
            cc = self.bf.next_byte()
            if cc == -1:
                return Token(EToken.EOF)

        # Now cc is either a delimiter or a regular character
        if cc == ord('('):
            # begin literal string
            self.parens = 1
            ls = self.get_literal_string()
            # cc is on the closing parens, call next_byte() so that when we
            # return, cc is the next not-yet-analyzed byte.
            self.cc = self.bf.next_byte()
            return Token(EToken.LITERAL_STRING, ls)
        elif cc == ord('<'):
            pos = self.bf.tell()
            cc2 = self.bf.next_byte()
            if cc2 == -1:
                # There's no byte to read
                return EToken.EOF
            if cc2 in TokenStream.hex_digit:
                # begin hex string
                self.bf.seek(pos)  # FIXME or I could pass on cc2
                hs = self.get_hex_string()
                # cc is on the closing 'greater than', call next_byte() so that
                # when we return, cc is the next not-yet-analyzed byte.
                self.cc = self.bf.next_byte()
                return Token(EToken.HEX_STRING, hs)
            elif cc2 == ord('<'):
                # begin dictionary
                self.cc = self.bf.next_byte()  # next byte to analyze
                return Token(EToken.DICT_BEGIN)
            else:
                # The initial '<' wasn't followed by expected data, this is an
                # error. 
                self.cc = self.bf.next_byte()
                return Token(EToken.ERROR,
                             "error: '<' not followed by hex digit or second '<'")
        elif cc == ord('>'):
            pos = self.bf.tell()  # useless ?
            cc2 = self.bf.next_byte()
            if cc2 == -1:
                # There's no byte to read
                return EToken.EOF
            elif cc2 == ord('>'):
                # end dictionary
                self.cc = self.bf.next_byte()
                return Token(EToken.DICT_END)
            else:
                # The initial '>' wasn't followed by expected data, this is an
                # error. 
                self.cc = self.bf.next_byte()
                return Token(EToken.ERROR,
                             "error: '>' not followed by a second '>'")
        elif cc == ord('/'):
            # begin name
            name = self.get_name()
            # self.cc is on a delimiter or whitespace, to be analyzed.
            return Token(EToken.NAME, name)
        elif cc == ord('%'):
            # begin comment
            pos = self.bf.tell()

            # Is it a version marker ?
            s = self.bf.next_byte(7)
            m = re.match(rb'PDF-(\d).(\d)', s)
            if m:
                self.cc = self.bf.next_byte()
                return Token(EToken.VERSION_MARKER,
                             (int(m.group(1)), int(m.group(2))))

            # Is it an EOF marker ?
            self.bf.seek(pos)
            s = self.bf.next_byte(4)
            if s == b'%EOF':
                self.cc = self.bf.next_byte()
                return Token(EToken.EOF_MARKER)

            # It's a comment, we need to ignore characters up to eol.
            self.bf.seek(pos)
            while True:
                # FIXME add a token type COMMENT and keep the value
                cc = self.bf.next_byte()
                if cc == ord('\r'):
                    # Do we have a \r\n pair ?
                    pos = self.bf.tell()
                    cc2 = self.bf.next_byte()
                    if cc2 == ord('\n'):
                        # we've found '\r\n', dos-style eol
                        self.cc = self.bf.next_byte()
                        return Token(EToken.CRLF)

                    # we've found '\r', mac-style eol
                    self.bf.seek(pos)
                    self.cc = self.bf.next_byte()  # could also do cc = cc2
                    return Token(EToken.CR)
                elif cc == ord('\n'):
                    # we've found '\n', unix-style eol
                    self.cc = self.bf.next_byte()
                    return Token(EToken.LF)
        elif cc == ord('['):
            self.cc = self.bf.next_byte()
            return Token(EToken.ARRAY_BEGIN)
        elif cc == ord(']'):
            self.cc = self.bf.next_byte()
            return Token(EToken.ARRAY_END)
        elif cc == ord('\r'):
            pos = self.bf.tell()
            cc2 = self.bf.next_byte()
            if cc2 == ord('\n'):
                # we've found '\r\n', dos-style eol
                self.cc = self.bf.next_byte()
                return Token(EToken.CRLF)
            # we've found '\r', mac-style eol
            self.bf.seek(pos)
            self.cc = self.bf.next_byte()
            return Token(EToken.CR)
        elif cc == ord('\n'):
            # we've found '\n', unix-style eol
            self.cc = self.bf.next_byte()
            return Token(EToken.LF)
        elif cc in b')>}':
            self.cc = self.bf.next_byte()
            return Token(EToken.ERROR,
                         "error: unexpected character '{c}'")
        else:
            # Neither whitespace nor delimiter, cc is a regular character.
            # Recognize keywords: true, false, null, obj, endobj, stream,
            # endstream, R, xref, trailer, startxref.
            # Recognize numbers
            # Here we should just recognize a run of regular characters.
            self.cc = cc
            return self.get_regular_run()
      
    #---------------------------------------------------------------------------
    # next_token
    #---------------------------------------------------------------------------
 
    def next_token(self):
        """Return the next token from the input stream."""
        # Invariant: cc has been read from the stream, but not yet analyzed. It
        # is stored (persisted in between calls) in self.cc. This means that
        # every time control leaves this function (through return), it must
        # read, but not analyze, the next character, and store it in sefl.cc.

        # Did we peek previously ?
        if len(self.peeked) > 0:
            return self.peeked.pop(0)  # self.peeked is a FIFO, not stack

        return self._next_token()
      
    #---------------------------------------------------------------------------
    # peek_token
    #---------------------------------------------------------------------------
 
    def peek_token(self):
        """Return the next token, without removing it from the input stream."""
        tok = self._next_token()
        self.peeked.append(tok)
        return tok
      
    #---------------------------------------------------------------------------
    # get_subsection_entry
    #---------------------------------------------------------------------------
 
    def get_subsection_entry(self):
        """Parse a subsection entry at this point in the stream."""
        # "Each entry shall be exactly 20 bytes long, including the end-of-line
        # marker."
        cc = self.cc

        # First byte has been read but nor analyzed, get the other 19
        s = bytearray()
        s.insert(0, cc)
        s += self.bf.next_byte(19)
        if s == -1:
            return Token(EToken.EOF)
        
        pat = b'(\d{10}) (\d{5}) ([nf])' + bEOLSP + b'$'
        m = re.match(pat, s)
        if not m:
            # I know the entry count, this should never happen
            cc = self.bf.next_byte()
            return Token(EToken.ERROR)
        x = int(m.group(1))  # offset, if in_use, or object number if free
        gen = int(m.group(2))
        in_use = m.group(3) == b'n'
        
        self.cc = self.bf.next_byte()
        return Token(EToken.SUBSECTION_ENTRY, (x, gen, in_use))
      
    #---------------------------------------------------------------------------
    # get_subsection_header
    #---------------------------------------------------------------------------
 
    # "The subsection shall begin with a line containing two numbers separated
    # by a SPACE (20h), denoting the object number of the first object in this
    # subsection and the number of entries in the subsection."

    # We don't know the number 

    def get_subsection_header(self):
        """Parse a subsection header at this point in the stream."""
        # Invariant: cc has been read from the stream, but not yet analyzed. It
        # is stored (persisted in between calls) in self.cc. This means that
        # every time control leaves this function (through return), it must
        # read, but not analyze, the next character, and store it in self.cc.
        cc = self.cc

        # Following the 'xref' keyword, en EOL marker token has been read, so
        # cc is the first character in the header line.

        # Save state in case we rollback
        save_cc = self.cc
        pos = self.bf.tell()

        # Get the first integer (first_objn), cf. get_regular_run())
        s = bytearray()
        while cc not in TokenStream.wspace:  # FIXME this is not robust enough
            s.append(cc)
            cc = self.bf.next_byte()
            if cc == -1:
                return Token(EToken.EOF)
        try:
            first_objn = int(s)
        except ValueError:
            # This could be an actual syntax error in the file, or it could be
            # that we reached the end of the last subsection, and the data
            # we've been reading is actually whatever follows the xref section.

            # Restore state, we want the entire line to be re-analyzed
            self.cc = save_cc
            self.bf.seek(pos)
            return Token(EToken.UNEXPECTED)

        # Move over the single space (FIXME should verify it ?)
        cc = self.bf.next_byte()
        if cc == -1:
            return Token(EToken.EOF)

        # Get the second integer (entry_cnt), cf. get_regular_run())
        s = bytearray()
        while cc not in [ord('\r'), ord('\n')]:
            s.append(cc)
            cc = self.bf.next_byte()
            if cc == -1:
                return Token(EToken.EOF)
        try:
            entry_cnt = int(s)
        except ValueError:
            # This could be an actual syntax error in the file, or it could be
            # that we reached the end of the last subsection, and the data
            # we've been reading is actually whatever follows the xref section.

            # Restore state, we want the entire line to be re-analyzed
            self.cc = save_cc
            self.bf.seek(pos)
            return Token(EToken.UNEXPECTED)

        # At this point, cc should be \r or \n, get the EOL marker
        self.cc = cc

        # This will parse CRLF, CR, or LF, or an error
        if cc == ord('\r'):
            pos2 = self.bf.tell()
            cc2 = self.bf.next_byte()
            if cc2 == -1:
                return Token(EToken.EOF)
            if cc2 != ord('\n'):
                # we've found '\r', mac-style eol
                self.bf.seek(pos2)
            # we've found '\r\n', dos-style eol
        elif cc != ord('\n'):
            # There's something else here that was not expected
            self.cc = save_cc
            self.bf.seek(pos)
            return Token(EToken.UNEXPECTED)
        # we've found '\n', unix-style eol

        # We've successfully parsed the entire line, we got the token, so we
        # must prepare the byte stream for the next token.
        
        self.cc = self.bf.next_byte()  # FIXME test EOF ?
        return Token(EToken.SUBSECTION_HDR, (first_objn, entry_cnt))

#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    print('This module is not meant to be executed directly.')
