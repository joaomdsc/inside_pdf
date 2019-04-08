#!/usr/bin/env python
# pdf.py - print out the pdf versions of every pdf file in a directory

import os
import re
import sys
from enum import Enum, auto, unique
import binfile

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
    PARSE_ERROR = auto()     # pseudo-token describing a parsing error 
    PARSE_EOF = auto()       # pseudo-token describing the EOF condition
    VERSION_MARKER = auto()  # %PDF-n.m
    EOF_MARKER = auto()      # %%EOF
    INTEGER = auto()
    REAL = auto()
    # I'm not sure I need to distinguish the next 2 tokens. Maybe just knowing
    # that its' a string will turn out to be enough.
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
            (maj, min) = self.data
            s += f'{maj}, {min}'
        elif self.type == EToken.INTEGER or self.type == EToken.REAL:
            s += str(self.data)
        elif self.type == EToken.LITERAL_STRING or self.type == EToken.HEX_STRING:
            # FIXME show character when displayable, \xyyyy otherwise
            s += self.data[:min(20, len(self.data))].hex()
        elif self.type == EToken.NAME:
            s += self.data.decode()
        elif self.type == EToken.PARSE_ERROR:
            s += self.data
        s += ')'
        return s

#-------------------------------------------------------------------------------
# class Tokener
#-------------------------------------------------------------------------------

class Tokener:
    # Character classes
    wspace = b'\0\t\f '
    # wspace = b'\0\t\n\r\f '
    delims = b'()<>[]{}/%'
    hex_digit = b'0123456789abcdefABCDEF'

    # Initializer
    def __init__(self, filepath, f):
        self.bf = binfile.BinFile(filepath, f)
        self.f = f
        self.parens = 0
        
    #---------------------------------------------------------------------------
    # get_literal_string
    #---------------------------------------------------------------------------

    def get_literal_string(self):
        """Found the opening paren, get the entire string."""
        # The opening parens did not go into ls. We have not yet read the
        # first character of the literal.
        ls = bytearray()
        while True:
            cc = self.bf.next_byte()
            c = chr(cc)
            if c == ')':
                self.parens -= 1
                if self.parens == 0:
                    # stack is empty, this was the closing parenthesis
                    # (it does not go into ls)
                    return ls
                else:
                    ls.append(cc)
            elif c == '(':
                self.parens += 1
                ls.append(cc)
            elif c == '\\':
                # Escape sequences
                cc2 = self.bf.peek_byte()
                c2 = chr(cc2)
                if c2 == 'n':
                    ls.append(ord('\n'))
                    self.bf.next_char()
                elif c2 == 'r':
                    ls.append(ord('\r'))
                    self.bf.next_char()
                elif c2 == 't':
                    ls.append(ord('\t'))
                    self.bf.next_char()
                elif c2 == 'b':
                    ls.append(ord('\b'))
                    self.bf.next_char()
                elif c2 == 'f':
                    ls.append(ord('\f'))
                    self.bf.next_char()
                elif c2 == '(':
                    ls.append(ord('('))
                    self.bf.next_char()
                elif c2 == ')':
                    ls.append(ord(')'))
                    self.bf.next_char()
                elif c2 == '\\':
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
            c = chr(cc)
            if c == '>':
                if len(hs)%2 == 1:
                    hs.append(ord('0'))
                # Each byte represents a hexadecimal digit, coded in ascii. If
                # I decode it, the resulting string will be suitable for fromhex())
                return bytes.fromhex(hs.decode())
            elif cc in Tokener.hex_digit:
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
            if cc in Tokener.delims or cc in Tokener.wspace or cc in b'\r\n':
                break
            c = chr(cc)
            if c == '#':
                # FIXME there may not be 2 characters left to read
                # FIXME handle error case when hc has invalid characters
                s = self.bf.peek_byte(2)
                if s[0] in Tokener.hex_digit and s[1] in Tokener.hex_digit:
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

    def get_regular_run(self, stream_len=None):
        """cc is a regular character, get the entire run of them."""
        # self.cc was analyzed by every handler in get_next_token, and not
        # recognized, so it's a regular character, and we want to accumulate
        # the entire consecutive run of regular characters.
        cc = self.cc
        
        run = bytearray()
        while (cc not in Tokener.delims and cc not in Tokener.wspace and
                   cc not in b'\r\n'):
            run.append(cc)
            cc = self.bf.next_byte()
        # cc now holds the first character not in 'run', still to be analyzed
            
        # Am I sure this is ASCII ?
        s = run.decode()
        #print(f'get_regular_run: s={s}')

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
                # Numeric objects
                # FIXME match vs. search. This leaves characters in s...
                m = re.match(r'[+-]?(\d+)', s)
                if m:
                    #print(f'm.group(1)={m.group(1)}, s="{s}"')
                    t = Token(EToken.INTEGER, int(m.group(1)))
                else:
                    # FIXME the below regexp is wrong
                    m = re.match(r'[+-]?([\d.]+)', s)
                    if m:
                        t = Token(EToken.REAL, float(s))
                    else:
                        self.cc = cc
                        return Token(EToken.PARSE_ERROR,
                                     "Unrecognized regular character run.")
            except ValueError:
                self.cc = cc
                return Token(EToken.PARSE_ERROR,
                             "Invalid string value for numeric parsing.")
        self.cc = cc
        return t
      
    #---------------------------------------------------------------------------
    # next_token
    #---------------------------------------------------------------------------
 
    def get_next_token(self, stream_len=None):
        """Get the next token. If stream_len == None, ignore it."""
        # Invariant: cc has been read from the stream, but not yet analyzed. It
        # is stored (persisted in between calls) in self.cc. This means that
        # every time control leaves this function (through return), it must
        # read, but not analyze, the next character, and store it in sefl.cc.
        cc = self.cc

        # Have we reached EOF ?
        if cc == -1:
            return Token(EToken.PARSE_EOF)

        # Start analyzing 
        while cc in Tokener.wspace:
            cc = self.bf.next_byte()
            if cc == -1:
                return Token(EToken.PARSE_EOF)

        # Now cc is either a delimiter or a regular character
        c = chr(cc)
        if c == '(':
            # begin literal string
            self.parens = 1
            ls = self.get_literal_string()
            # cc is on the closing parens, call next_byte() so that when we
            # return, cc is the next not-yet-analyzed byte.
            self.cc = self.bf.next_byte()
            return Token(EToken.LITERAL_STRING, ls)
        elif c == '<':
            cc2 = self.bf.peek_byte()
            c2 = chr(cc2)
            if cc2 == -1:
                # There's no byte to peek at
                # FIXME this is an error situation
                return -1
            if cc2 in Tokener.hex_digit:
                # begin hex string
                hs = self.get_hex_string()
                # cc is on the closing 'greater than', call next_byte() so that
                # when we return, cc is the next not-yet-analyzed byte.
                self.cc = self.bf.next_byte()
                return Token(EToken.HEX_STRING, hs)
            elif c2 == '<':
                # begin dictionary
                self.bf.next_byte()  # move input stream forward, past peeked char
                self.cc = self.bf.next_byte()  # next byte to analyze
                return Token(EToken.DICT_BEGIN)
            else:
                # The initial '<' wasn't followed by expected data, this is an
                # error. 
                self.cc = self.bf.next_byte()
                return Token(EToken.PARSE_ERROR,
                             "error: '<' not followed by hex digit or second '<'")
        elif c == '>':
            cc2 = self.bf.peek_byte()
            c2 = chr(cc2)
            if cc2 == -1:
                # There's no byte to peek at
                # FIXME this is an error situation
                return -1
            elif c2 == '>':
                # end dictionary
                self.bf.next_byte()  # read the one I've peeked
                self.cc = self.bf.next_byte()
                return Token(EToken.DICT_END)
            else:
                # The initial '>' wasn't followed by expected data, this is an
                # error. 
                self.cc = self.bf.next_byte()
                return Token(EToken.PARSE_ERROR,
                             "error: '>' not followed by a second '>'")
        elif c == '/':
            # begin name
            name = self.get_name()
            # self.cc is on a delimiter or whitespace, to be analyzed.
            return Token(EToken.NAME, name)
        elif c == '%':
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
                # print(f'%: cc={cc}', end='')
                # if 32 <= cc <= 126:
                #     print(f' {chr(cc)}', end='')
                # print()
                c2 = chr(cc)
                if c2 == '\r':
                    cc2 = self.bf.peek_byte()
                    c3 = chr(cc2)
                    if c3 == '\n':
                        # we've found '\r\n', dos-style eol
                        self.bf.next_byte()  # move forward over the peeked char
                        self.cc = self.bf.next_byte()
                        return Token(EToken.CRLF)
                    # we've found '\r', mac-style eol
                    self.cc = self.bf.next_byte()
                    return Token(EToken.CR)
                elif c2 == '\n':
                    # we've found '\n', unix-style eol
                    self.cc = self.bf.next_byte()
                    return Token(EToken.LF)
        elif c == '[':
            state = 'begin_array'
            self.cc = self.bf.next_byte()
            return Token(EToken.ARRAY_BEGIN)
        elif c == ']':
            state = 'end_array'
            self.cc = self.bf.next_byte()
            return Token(EToken.ARRAY_END)
        elif c == '\r':
            cc2 = self.bf.peek_byte()
            c2 = chr(cc2)
            if c2 == '\n':
                # we've found '\r\n', dos-style eol
                self.bf.next_byte()  # move forward over the peeked char
                self.cc = self.bf.next_byte()
                return Token(EToken.CRLF)
            # we've found '\r', mac-style eol
            self.cc = self.bf.next_byte()
            return Token(EToken.CR)
        elif c == '\n':
            # we've found '\n', unix-style eol
            self.cc = self.bf.next_byte()
            return Token(EToken.LF)
        elif c in ')>}':
            self.cc = self.bf.next_byte()
            return Token(EToken.PARSE_ERROR,
                         "error: unexpected character '{c}'")
        else:
            # Neither whitespace nor delimiter, cc is a regular character.
            # Recognize keywords: true, false, null, obj, endobj, stream,
            # endstream, R, xref, trailer, startxref.
            # Recognize numbers
            # Here we should just recognize a run of regular characters.
            self.cc = cc
            return self.get_regular_run(stream_len)

#-------------------------------------------------------------------------------
# parse_tokens
#-------------------------------------------------------------------------------

def parse_tokens(filepath):
    # Array for token storage 
    tokens = []

    # Parse a character stream into a token stream
    with open(filepath, 'rb') as f:
        tk = Tokener(filepath, f)
        tk.cc = tk.bf.next_byte()
        stream_len = -1
        while True:
            t = tk.get_next_token(stream_len)
            if t.type == EToken.PARSE_EOF:
                break
            print(t)
            tokens.append(t)
            # The definition of stream forces us to start building higher-level
            # objects before the entire token stream ahs been parsed. The
            # number of bytes in the stream is declared in the stream
            # dictionary that *precedes* it. So I need to build dictionaries as
            # they appear.
            if t.type == EToken.DICT_BEGIN:
                while True:
                    # The dictionary entry's key
                    t = tk.get_next_token()
                    if t.type == EToken.DICT_END:
                        break
                    if t.type != EToken.NAME:
                        print('error')
                        break
                    print(t)
                    tokens.append(t)
                    k = t.data.decode()  # FIXME assuming only ascii
                    
                    # The dictionary entry's value
                    t = tk.get_next_token()
                    if t.type == EToken.PARSE_EOF:
                        print('error')
                        break
                    print(t)
                    tokens.append(t)

                    if k == 'Length':
                        if t.type != EToken.INTEGER:
                            print('error')
                            break
                        stream_len = t.data
                        break
                    

    # # Now print out the tokens
    # for t in tokens:
    #     print(t)


#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    # Check cmd line args
    if len(sys.argv) < 2:
        print(f'usage: {sys.argv[0]} <filepath>')
        exit(-1)
    filepath = sys.argv[1]
    
    parse_tokens(filepath)

    # Notes: the flex_bison.pdf has some unexpected data:
    #
    # <</Contents 6624 0 R /CropBox[ 0 0 595.276 841.89]/MediaBox[ 0 0 504 661.44]
    #
    # In a dictionary entry, the value may be a indirect reference, i.e. 3
    # tokens INTEGER, INTEGER, OBJ_REF.

    # The problem with streams is that we need to parse a higher-level object,
    # the dictionary, to get the length of the stream. So it mixes the lexical
    # and grammatical levels. The only way to move forward is to code the
    # grammer parser in parallel with the lexical parser: the token stream
    # needs to be parsed into higher-level objects on-the-fly, as tokens are
    # retrieved. This will probably require a token lookahead mechanism.

    # Also, when a dictionary has been parsed (up to the end-of-dict token)
    # that includes a /Length key, and this dictionary is immediately followed
    # by an optional EOL token, then a STREAM_BEGIN token, and finally a CRLF
    # or LF (but not CR), at that point the grammar level must hand down the
    # length information to the lexical parser, so it can read the bytes in the
    # stream.

    # The BinFile must be tested for reading a very large number of bytes as
    # compared to the block size.
