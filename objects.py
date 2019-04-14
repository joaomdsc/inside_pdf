#!/usr/bin/env python
# objects.py - parse a stream of bytes into a stream of PDF spec tokens

import os
import re
import sys
from enum import Enum, auto, unique
import binfile
from tokener import Tokener, EToken

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
            (major, minor) = self.data
            s += f'{major}, {minor}'
        elif self.type == EToken.INTEGER or self.type == EToken.REAL:
            s += str(self.data)
        elif self.type == EToken.LITERAL_STRING or self.type == EToken.HEX_STRING:
            s += self.data[:len(self.data)].decode('unicode_escape')
        elif self.type == EToken.NAME:
            # FIXME non ascii bytes may be found in here
            s += self.data.decode()
        elif self.type == EToken.PARSE_ERROR:
            s += self.data
        s += ')'
        return s

#-------------------------------------------------------------------------------
# class ObjStream
#-------------------------------------------------------------------------------

class ObjStream:

    # Initializer
    def __init__(self, filepath, f):
        self.tk = Tokener(filepath, f)
        self.f = f
        self.tok = None
      
    #---------------------------------------------------------------------------
    # next_object
    #---------------------------------------------------------------------------
 
    def next_object(self):
        """Get the next object."""
        # Invariant: tok has been read from the stream, but not yet analyzed. It
        # is stored (persisted in between calls) in self.tok. This means that
        # every time control leaves this function (through return), it must
        # read, but not analyze, the next token, and store it in self.tok.
        tok = self.tok

        # Have we reached EOF ?
        if tok == Token(EToken.PARSE_EOF):
            return obj_eof

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
            if cc2 in Tokener.hex_digit:
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
                return Token(EToken.PARSE_ERROR,
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
                return Token(EToken.PARSE_ERROR,
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
            return Token(EToken.PARSE_ERROR,
                         "error: unexpected character '{c}'")
        else:
            # Neither whitespace nor delimiter, cc is a regular character.
            # Recognize keywords: true, false, null, obj, endobj, stream,
            # endstream, R, xref, trailer, startxref.
            # Recognize numbers
            # Here we should just recognize a run of regular characters.
            self.cc = cc
            return self.get_regular_run()

#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    print('This module is not meant to be executed directly.')
