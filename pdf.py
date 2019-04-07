#!/usr/bin/env python
# pdf.py - print out the pdf versions of every pdf file in a directory

import os
import re
import sys
from enum import Enum, auto, unique
from file_read_backwards import FileReadBackwards
import binfile

EOL = '(\r\n|\r|\n)'
bEOL = b'(\r\n|\r|\n)'

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
    VERSION_MARKER = auto()  # %PDF-n.m
    EOF_MARKER = auto()      # %%EOF
    TRUE = auto()            # true
    FALSE = auto()           # false
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
    STREAM_BEGIN = auto()    # '<<'
    STREAM_END = auto()      # '>>'
    NULL = auto()            # null
    OBJECT_BEGIN = auto()    # '<<'
    OBJECT_END = auto()      # '>>'
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

#-------------------------------------------------------------------------------
# class Tokenizer
#-------------------------------------------------------------------------------

class Tokenizer:

    hex_digit = b'0123456789abcdefABCDEF'

    def __init__(self, filepath):
        self.pb = BinFile(filepath)
        self.parens = 0
        
    #---------------------------------------------------------------------------
    # get_literal_string
    #---------------------------------------------------------------------------

    def get_literal_string(self):
        """Found the opening paren, get the entire string."""
        # The opening parens did not go into ls 
        ls = b''
        while True:
            cc = self.pb.next_byte()
            c = chr(cc)
            if c == ')':
                self.parens -= 1
                if self.parens == 0:
                    # stack is empty, this was the closing parenthesis
                    # (it does not go into ls)
                    return ls
                else:
                    ls += cc
            elif c == '(':
                self.parens += 1
                ls += cc
            elif c == '\\':
                # Escape sequences
                cc2 = self.pb.peek_byte()
                c2 = chr(cc2)
                if c2 == 'n':
                    ls += ord('\n')
                elif c2 == 'r':
                    ls += ord('\r')
                elif c2 == 't':
                    ls += ord('\t')
                elif c2 == 'b':
                    ls += ord('\b')
                elif c2 == 'f':
                    ls += ord('\f')
                elif c2 == '(':
                    ls += ord('(')
                elif c2 == ')':
                    ls += ord(')')
                elif c2 == '\\':
                    ls += ord('\\')
                else:
                    pass
                    # # peek may fail if there are less than 3 characters in the
                    # # stream. In that case, the backslash should be ignored,
                    # # and the following character(s) read.
                    # oc = self.peek(3)
                    # try:
                    #     c = int(oc, 8)
                    #     self.s += c  # FIXME is this correct ??
                    #     # FIXME need to consume 3 caracters from the input stream
                    # except ValueError as e:
                    #     # Backslash was not followed by one of the expected
                    #     # characters, just ignore it.
                    #     pass
            else:
                # All other characters just get added to the string
                ls += cc

    #---------------------------------------------------------------------------
    # get_hex_string
    #---------------------------------------------------------------------------

    def get_hex_string(self):
        """Found the opening 'less than', now get the entire string.

        This actually returns a bytes object, since the hex digits can represent
        any value between 0 and 255, it's not necessarily ascii.
"""
        
        # The opening 'less than' did not go into the hex string 'hs' 
        hs = b''
        while True:
            cc = self.pb.next_byte()
            c = chr(cc)
            if c == '>':
                if len(hs)%2 == 1:
                    hs += '0'
                # Each byte represents a hexadecimal digit, coded in ascii. If
                # I decode it, the resulting string will be suitable for fromhex())
                return bytes.fromhex(hs.decode())
            elif cc in Tokenizer.hex_digit:
                hs += cc
            else:
                # Incorrect value
                return None

    #---------------------------------------------------------------------------
    # get_name
    #---------------------------------------------------------------------------

    def get_name(self):
        """Found the opening '/', now get the rest of the characters."""
        # cc is the '/'. If there are delimiters or whitespace
        s = ''
        while True:
            cc = self.pb.next_byte()
            if cc in Tokenizer.delims or cc in Tokenizer.wspace:
                break
            c = chr(cc)
            if c == '#':
                # FIXME there may not be 2 characters left to read
                # FIXME handle error case when hc has invalid characters
                hc = self.pb.next_byte(2)
                s += bytes.fromhex(hc)
                continue
            if cc < 33 or cc > 126:
                # Cf. PDF Spec 1.7 page 17
                print('error: character should be written using its 2-digit'
                      + ' hexadecimal code, preceded by the NUMBER SIGN only.')
                return ''
            s += cc

        return s
            
    #---------------------------------------------------------------------------
    # next_token
    #---------------------------------------------------------------------------
 
    def get_next_token(self):
        """Get the next token."""
        # Invariant: I've recognized a token, so cc is either whitespace or a
        # delimiter character
        while cc in BinFile.wspace:
            cc = self.pb.next_byte()
            if cc == -1:
                return -1
        # Now cc is either a delimiter or a regular character
        c = chr(cc)
        if c == '(':
            # begin literal string
            self.parens = 1
            ls = self.get_literal_string()
            t = Token(EToken.LITERAL_STRING, ls)
            # cc is on the closing parens, call next_byte() so that when we
            # return, cc is the next not-yet-analyzed byte.
            cc = self.pb.next_byte()
            if cc == -1:
                # FIXME reached eof, how do I handle this ?
                # FIXME what about t ?
                return -1
            # Now return a Token object
            return t
        elif c == '<':
            cc2 = self.pb.peek_byte()
            if cc2 == -1:
                # There's no byte to peek at
                # FIXME this is an error situation
                return -1
            if cc2 in Tokenizer.hex_digit:
                # I'll get this hex digit again from next_byte())
                # begin hex string
                hs = self.get_hex_string()
                t = Token(EToken.HEX_STRING, hs)
                # cc is on the closing 'greater than', call next_byte() so that
                # when we return, cc is the next not-yet-analyzed byte.
                cc = self.pb.next_byte()
                if cc == -1:
                    # FIXME reached eof, how do I handle this ?
                    # FIXME what about t ?
                    return -1
                # Now return a Token object
                return t
            elif cc2 == '<':
                # begin dictionary, next byte is '<' 
                cc = self.pb.next_byte()
                return Token(EToken.DICT_BEGIN)
            else:
                # The initial '<' wasn't followed by expected data, this is an
                # error. This is exactly why I peeked, so the next character is
                # available for analysis in the normal context.
                print("error: '<' not followed by a second '<'")
        elif c == '>':
            cc2 = self.pb.peek_byte()
            if cc2 == -1:
                # There's no byte to peek at
                # FIXME this is an error situation
                return -1
            elif cc2 == '>':
                # end dictionary
                cc = self.pb.next_byte()
                return Token(EToken.DICT_END)
            else:
                # The initial '>' wasn't followed by expected data, this is an
                # error. This is exactly why I peeked, so the next character is
                # available for analysis in the normal context.
                print("error: '>' not followed by a second '>'")
        elif c == '/':
            # begin name
            s = self.get_name()
            # I've stopped on a delimiter or whitespace
            # FIXME either next_byte() here, or what ?
        elif c == '%':
            # FIXME recognize special cases %PDF-n.m, %%EOF
            while True:
                # next_byte() here mustn't handle end of lines transparently,
                # we need to ignore characters up to eol.
                cc = self.pb.next_byte()
                if cc == '\r':
                    cc2 = self.pb.peek_byte()
                    if cc2 == '\n':
                        cc = self.pb.next_byte()
                        # we've found '\r\n', eol
                    # we've found '\r', eol
                elif cc = '\n':
                    # we've found '\r', eol
                    pass
        elif cc == '[':
            state = 'begin_array'
        elif cc in b')>]}':
            print('error: unexpected character')
        else:
            # Neither whitespace nor delimiter, cc is a regular character.
            # Recognize keywords: true, false, null, obj, endobj, stream,
            # endstream, R, xref, n, f, trailer, startxref. Here we should just
            # recognize a run of regular characters.
            
            # Recognize numbers

        # Indirect objects are higher-level objects : number number R
                
#-------------------------------------------------------------------------------
# get_eol
#-------------------------------------------------------------------------------

def get_eol(filepath):
    """Determine the type of line endings in this file."""
    with open(filepath, 'rb') as f:
        line = f.readline()
    m = re.match(rb'%PDF-\d.\d\r\n', line)
    if m:
        return 'CRLF'
    else:
        m = re.match(rb'%PDF-\d.\d\r', line)
        if m:
            return 'CR'
        else:
            m = re.match(rb'%PDF-\d.\d\n', line)
            if m:
                return 'LF'
    return ''

#-------------------------------------------------------------------------------
# get_version
#-------------------------------------------------------------------------------

def get_version(filepath):
    """Extract the PDF Specification version number."""
    with open(filepath, 'rb') as f:
        line = f.readline()
            
        # Adding '$' at the end of the regexp causes it to fail for some
        # files. It correctly matches files that use the Unix-style line
        # ending 0a (\n, LF), but fails on files that use Mac-style 0d (\r,
        # CR) or Windows-style 0d0a (\r\n, CRLF)

        m = re.match(b'^%PDF-([0-9]).([0-9])' + bEOL, line)
        if m:
            return int(m.group(1)), int(m.group(2))
        else:
            return 0, 0

#-------------------------------------------------------------------------------
# get_trailer - read file from the end, extract trailer dict and xref offset
#-------------------------------------------------------------------------------

def get_trailer(filepath):
    """Extract the trailer dictionary and xref offset."""
    offset = -1
    trailer = False
    
    with FileReadBackwards(filepath) as f:
        # Last line
        line = f.readline()
        m = re.match('%%EOF' + EOL, line)
        if not m:
            print('syntax error: no EOF marker')

        # Byte offset of last cross-reference section
        line = f.readline().rstrip()
        offset = int(line)

        # startxref
        line = f.readline()
        m = re.match('startxref' + EOL, line)
        if not m:
            print('syntax error: no startxref')

        # end of trailer dictionary
        line = f.readline()
        m = re.search('>>' + EOL, line)
        if m:
            trailer = True
            
    return trailer, offset 

#-------------------------------------------------------------------------------
# get_indirect_objects
#-------------------------------------------------------------------------------

# FIXME need to properly tokenize my parsing algorithm, that's how the spec is
# done, not by lines.

def get_indirect_objects(filepath):
    """Extract all the indirect objects from the beginning up to the trailer."""
    with open(filepath, 'rb') as f:
        objs = []
        for line in f:
            # FIXME I'm using python re's notion of whitespace, not the PDF
            # specification's.
            m = re.match(rb'(\d+)\s+(\d+)\s+obj' + bEOL, line)
            if m:
                # Start a new object (object number, generation nbr)
                obj = PdfObj(int(m.group(1).decode()), int(m.group(2).decode()))
                continue
            m = re.match(b'endobj' + bEOL, line)
            if m:
                # Finish the current object
                objs.append(obj)
                
            m = re.match(b'<<', line)
            if m:
                # Finish the current object
                pass
               
#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    # path = r'C:\Users\joao.moreira.INV\OneDrive - INVIVOO\Books'
    path = r'C:\u\pdf'
    print('Filename;Version;EOL;Trailer;Offset')
    for f in os.listdir(path):
        if f.endswith('.pdf'):
            filepath = os.path.join(path, f)
            eol = get_eol(filepath)
            major, minor = get_version(filepath)
            trailer, offset = get_trailer(filepath)
            print(f'{f};{major}.{minor};{eol:4};{" true" if trailer else "false"}'
                  + f';{offset:8}')
