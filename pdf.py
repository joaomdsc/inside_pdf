#!/usr/bin/env python
# pdf.py - print out the pdf versions of every pdf file in a directory

import os
import re
import sys
from enum import Enum, auto, unique
from token_stream import EToken, TokenStream
from object_stream import EObject, ObjectStream

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
        tk = TokenStream(filepath, f)
        # tk.cc = tk.bf.next_byte()
        indent = 0
        while True:
            t = tk.next_token()
            if t.type == EToken.EOF:
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
        ob = ObjectStream(filepath, f)
        indent = 0
        while True:
            o = ob.next_object()
            if o.type == EObject.EOF:
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
