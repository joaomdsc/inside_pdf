#!/usr/bin/env python
# pdf.py - print out the pdf versions of every pdf file in a directory

import os
import re
import sys
from enum import Enum, auto, unique
import binfile
from tokener import Tokener, EToken
from objects import ObjStream, EObject

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
# parse_tokens
#-------------------------------------------------------------------------------

def parse_tokens(filepath):
    # Array for token storage 
    tokens = []

    # Parse a character stream into a token stream
    with open(filepath, 'rb') as f:
        tk = Tokener(filepath, f)
        # tk.cc = tk.bf.next_byte()
        indent = 0
        while True:
            t = tk.next_token()
            if t.type == EToken.PARSE_EOF:
                break
            if t.end():
                indent -= 1
            t.print_indented(indent)
            if t.begin():
                indent += 1

            tokens.append(t)

#-------------------------------------------------------------------------------
# parse_objects
#-------------------------------------------------------------------------------

def parse_objects(filepath):
    # Array for object storage 
    objects = []

    # Parse a character stream into a object stream
    with open(filepath, 'rb') as f:
        ob = ObjStream(filepath, f)
        indent = 0
        while True:
            o = ob.next_object()
            if o.type == EObject.PARSE_EOF:
                break
            print(o)
            objects.append(o)

#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    # Check cmd line args
    if len(sys.argv) < 2:
        print(f'usage: {sys.argv[0]} <filepath>')
        exit(-1)
    filepath = sys.argv[1]
    
    # parse_tokens(filepath)
    parse_objects(filepath)

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
