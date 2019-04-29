#!/usr/bin/env python
# token_stream.py - parse a stream of PDF spec tokens from a stream of bytes

import os
import re
import sys
from enum import Enum, auto, unique
import byte_stream

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
    ERROR = auto()           # pseudo-token describing a parsing error 
    EOF = auto()             # pseudo-token describing the EOF condition
    VERSION_MARKER = auto()  # %PDF-n.m
    EOF_MARKER = auto()      # %%EOF
    INTEGER = auto()
    REAL = auto()
    # I'm not sure I need to distinguish the next 2 tokens. Maybe just knowing
    # that it's a string will turn out to be enough.
    LITERAL_STRING = auto()  # (xxxxx) FIXME maybe a single STRING token ?
    HEX_STRING = auto()      # <xxxxx>
    NAME = auto()            # /xxxxx
    ARRAY_BEGIN = auto()     # '['
    ARRAY_END = auto()       # ']'
    DICT_BEGIN = auto()      # '<<'
    DICT_END = auto()        # '>>'
    TRUE = auto()            # true
    FALSE = auto()           # false
    NULL = auto()            # null
    OBJECT_BEGIN = auto()    # obj
    OBJECT_END = auto()      # endobj
    STREAM_BEGIN = auto()    # stream
    STREAM_END = auto()      # endstream
    OBJ_REF = auto()         # 'R'
    XREF_SECTION = auto()    # xref
    TRAILER = auto()         # trailer
    STARTXREF = auto()       # startxref
    CR = auto()              # carriage return, \r, 0d
    LF = auto()              # newline, \n, 0a
    CRLF = auto()            # \r\n, 0d0a

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
        self.bf = byte_stream.ByteStream(filepath, f)
        self.f = f
        self.cc = self.bf.next_byte()
        self.parens = 0
        self.peeked = []

    def reset(self, offset):
        self.bf.reset(offset)
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
                cc2 = self.bf.peek_byte()
                if cc2 == ord('n'):
                    ls.append(ord('\n'))
                    self.bf.next_char()
                elif cc2 == ord('r'):
                    ls.append(ord('\r'))
                    self.bf.next_char()
                elif cc2 == ord('t'):
                    ls.append(ord('\t'))
                    self.bf.next_char()
                elif cc2 == ord('b'):
                    ls.append(ord('\b'))
                    self.bf.next_char()
                elif cc2 == ord('f'):
                    ls.append(ord('\f'))
                    self.bf.next_char()
                elif cc2 == ord('('):
                    ls.append(ord('('))
                    self.bf.next_char()
                elif cc2 == ord(')'):
                    ls.append(ord(')'))
                    self.bf.next_char()
                elif cc2 == ord('\\'):
                    ls.append(ord('\\'))
                    self.bf.next_char()
                else:
                    # peek may fail if there are less than 3 characters in the
                    # stream. In that case, the backslash should be ignored,
                    # and the following character(s) read.
                    s = self.bf.peek_byte(3)
                    try:
                        c = int(s, 8)
                        ls.append(c)
                        self.bf.next_char(3)
                    except ValueError as e:
                        # Backslash was not followed by one of the expected
                        # characters, just ignore it. The character following
                        # the backslash wasn't read.
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
                s = self.bf.peek_byte(2)
                if s[0] in TokenStream.hex_digit and s[1] in TokenStream.hex_digit:
                    name += bytes.fromhex(s.decode())
                    self.bf.next_byte(2)
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
        
        run = bytearray()
        while (cc not in TokenStream.delims and cc not in TokenStream.wspace and
                   cc not in b'\r\n'):
            run.append(cc)
            cc = self.bf.next_byte()
        # cc now holds the first character not in 'run', still to be analyzed
            
        # FIXME am I sure this is ASCII ?
        s = run.decode()

        if s == 'true':
            t = Token(EToken.TRUE)
        elif s == 'false':
            t = Token(EToken.FALSE)
        elif s == 'null':
            t = Token(EToken.NULL)
        elif s == 'obj':
            t = Token(EToken.OBJECT_BEGIN)
        elif s == 'endobj':
            t = Token(EToken.OBJECT_END)
        elif s == 'stream':
            t = Token(EToken.STREAM_BEGIN)
            # PDF Spec, § 7.3.8.1, page 19 :"The keyword stream that follows
            # the stream dictionary shall be followed by an end-of-line marker
            # consisting of either a CARRIAGE RETURN and a LINE FEED or just a
            # LINE FEED, and not by a CARRIAGE RETURN alone."
        elif s == 'endstream':
            t = Token(EToken.STREAM_END)
        elif s == 'R':
            t = Token(EToken.OBJ_REF)
        elif s == 'xref':
            t = Token(EToken.XREF_SECTION)
        elif s == 'trailer':
            t = Token(EToken.TRAILER)
        elif s == 'startxref':
            t = Token(EToken.STARTXREF)
        else:
            try:
                t = Token(EToken.INTEGER, int(s))
            except ValueError:
                try:
                    t = Token(EToken.REAL, float(s))
                except ValueError:
                    self.cc = cc
                    return Token(EToken.ERROR,
                                 "Unrecognized regular character run.")              
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
            cc2 = self.bf.peek_byte()
            if cc2 == -1:
                # There's no byte to peek at
                # FIXME this is an error situation
                return -1
            if cc2 in TokenStream.hex_digit:
                # begin hex string
                hs = self.get_hex_string()
                # cc is on the closing 'greater than', call next_byte() so that
                # when we return, cc is the next not-yet-analyzed byte.
                self.cc = self.bf.next_byte()
                return Token(EToken.HEX_STRING, hs)
            elif cc2 == ord('<'):
                # begin dictionary
                self.bf.next_byte()  # move input stream forward, past peeked char
                self.cc = self.bf.next_byte()  # next byte to analyze
                return Token(EToken.DICT_BEGIN)
            else:
                # The initial '<' wasn't followed by expected data, this is an
                # error. 
                self.cc = self.bf.next_byte()
                return Token(EToken.ERROR,
                             "error: '<' not followed by hex digit or second '<'")
        elif cc == ord('>'):
            cc2 = self.bf.peek_byte()
            if cc2 == -1:
                # There's no byte to peek at
                # FIXME this is an error situation
                return -1
            elif cc2 == ord('>'):
                # end dictionary
                self.bf.next_byte()  # read the one I've peeked
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
            s = self.bf.peek_byte(7)
            m = re.match(rb'PDF-(\d).(\d)', s)
            if m:
                self.bf.next_byte(7)  # move forward over the peeked chars
                self.cc = self.bf.next_byte()
                return Token(EToken.VERSION_MARKER,
                             (int(m.group(1)), int(m.group(2))))
            s = self.bf.peek_byte(4)
            if s == b'%EOF':
                self.bf.next_byte(4)  # move forward over the peeked chars
                self.cc = self.bf.next_byte()
                return Token(EToken.EOF_MARKER)
            while True:
                # FIXME add a token type COMMENT and keep the value
                # we need to ignore characters up to eol.
                cc = self.bf.next_byte()
                if cc == ord('\r'):
                    cc2 = self.bf.peek_byte()
                    if cc2 == ord('\n'):
                        # we've found '\r\n', dos-style eol
                        self.bf.next_byte()  # move forward over the peeked char
                        self.cc = self.bf.next_byte()
                        return Token(EToken.CRLF)
                    # we've found '\r', mac-style eol
                    self.cc = self.bf.next_byte()
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
            cc2 = self.bf.peek_byte()
            if cc2 == ord('\n'):
                # we've found '\r\n', dos-style eol
                self.bf.next_byte()  # move forward over the peeked char
                self.cc = self.bf.next_byte()
                return Token(EToken.CRLF)
            # we've found '\r', mac-style eol
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

#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    print('This module is not meant to be executed directly.')
