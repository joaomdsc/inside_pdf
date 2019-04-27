#!/usr/bin/env python
# object_stream.py - parse a stream of PDF spec objects from a stream of tokens

import os
import re
import sys
from enum import Enum, auto, unique
from token_stream import EToken, TokenStream

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
#  EObject
#-------------------------------------------------------------------------------

# Possible object types in PDF files
@unique
class EObject(Enum):
    ERROR = auto()     # pseudo-object describing a parsing error 
    EOF = auto()       # pseudo-object describing the EOF condition
    BOOLEAN = auto()
    INTEGER = auto()
    REAL = auto()
    STRING = auto()
    NAME = auto()
    ARRAY = auto()
    DICTIONARY = auto()
    STREAM = auto()
    NULL = auto()
    IND_OBJ_DEF = auto()    # indirect object definition
    IND_OBJ_REF = auto()    # indirect object reference

    def __str__(self):
        """Print out 'NAME' instead of 'EToken.NAME'."""
        return self.name

#-------------------------------------------------------------------------------
# class PdfObject
#-------------------------------------------------------------------------------

class PdfObject():
    """PDF objects are parsed from the input token stream."""
    def __init__(self, type, data=None):
        self.type = type
        self.data = data

    def __str__(self):
        s = f'{self.type}('
        if self.type in [EObject.BOOLEAN, EObject.INTEGER, EObject.REAL]:
            s += f'{self.data}'
        elif self.type == EObject.STRING or self.type == EObject.NAME:
            s += self.data[:len(self.data)].decode('unicode_escape')
        elif self.type == EObject.ARRAY:
            s += '['
            for x in self.data:
                s += f'{x}, '
            s += ']'
        elif self.type == EObject.DICTIONARY:
            s += '{'
            for k, v in self.data.items():
                s += f'({k}, {v}), '
            s += '}'
        elif self.type == EObject.IND_OBJ_REF:
            s += f"{self.data['objn']} {self.data['gen']} R"
        s += ')'
        return s

#-------------------------------------------------------------------------------
# class ObjectStream
#-------------------------------------------------------------------------------

class ObjectStream:

    # Initializer
    def __init__(self, filepath, f):
        self.tk = TokenStream(filepath, f)
        self.f = f
        self.tok = self.tk.next_token()

    def reset(self, offset):
        self.tk.reset(offset)
        # Normal init
        self.tok = self.tk.next_token()
      
    #---------------------------------------------------------------------------
    # get_array
    #---------------------------------------------------------------------------
 
    def get_array(self):
        """Found the opening ARRAY_BEGIN token, now get the entire array."""
        # Arrays can hold any kind of objects, including other arrays and
        # dictionaries.

        # Prepare an array object
        arr = []

        tok = self.tk.next_token()
        while True:
            if tok.type == EToken.ARRAY_END:
                # It's a python array, but the elements are PdfObjects
                return PdfObject(EObject.ARRAY, arr)
            self.tok = tok
            obj = self.next_object()
            tok = self.tok
            # The next token is already stored in self.tok, but it hasn't been
            # analyzed yet.
            arr.append(obj)
      
    #---------------------------------------------------------------------------
    # get_dictionary
    #---------------------------------------------------------------------------
 
    def get_dictionary(self):
        """Found the opening DICT_BEGIN token, now get the entire dictionary."""
        # Dictionaries are sets of (key, value) pairs, where the value can be
        # any kind of object, including arrays and other dictionaries.

        # Prepare a dictionary object
        d = {}

        #=======================================================================
        # FIXME line breaks inside a dictionary are not recognized
        #=======================================================================

        tok = self.tk.next_token()
        while True:
            if tok.type == EToken.DICT_END:
                # It's a python dictionary, but the values are PdfObjects
                return PdfObject(EObject.DICTIONARY, d)
            if tok.type == EToken.NAME:
                tok2 = self.tk.next_token()
                self.tok = tok2
                obj = self.next_object()
                # FIXME: what if there was some object it couldn't parse ?
                # i.e. handle ERROR and EOF
                # FIXME: can any bytes object be decoded like this ?
                # FIXME: I've lost the keys' original bytes object
                d[tok.data.decode('unicode_escape')] = obj            

                # The next token is already stored in self.tok, but it hasn't
                # been analyzed yet.
                tok = self.tok
            elif tok.type in [EToken.CR, EToken.LF, EToken.CRLF]:
                tok = self.tk.next_token()
            else:
                return PdfObject(EObject.ERROR)
      
    #---------------------------------------------------------------------------
    # next_object
    #---------------------------------------------------------------------------
 
    def next_object(self):
        """Get the next object as a PdfObject."""
        # Invariant: tok has been read from the stream, but not yet analyzed. It
        # is stored (persisted in between calls) in self.tok. This means that
        # every time control leaves this function (through return), it must
        # read, but not analyze, the next token, and store it in self.tok.
        tok = self.tok

        # Ignore CRLF (why do I parse the tokens then ?)
        while tok.type in [EToken.CR, EToken.LF, EToken.CRLF]:
            tok = self.tok = self.tk.next_token()
        
        # Have we reached EOF ?
        if tok.type == EToken.EOF:
            return PdfObject(EObject.EOF)
        elif tok.type == EToken.ERROR:
            return PdfObject(EObject.ERROR)

        # Now analyze tok: is it a boolean ?
        elif tok.type == EToken.TRUE:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.BOOLEAN, True)
        elif tok.type == EToken.FALSE:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.BOOLEAN, False)

        # Is it an integer number ?
        elif tok.type == EToken.INTEGER:
            # Attempt to find the longest match first. Object definitions and
            # references are two integers plus another token, they must be
            # parsed first, and if not found, then we'll settle for the simple
            # integer.
            
            # Lookahead 1 token. If we find another integer, keep looking.
            # If we find an OBJECT_BEGIN, then we have an indirect object
            # definition.
            # If we find an OBJ_REF, then we have an indirect reference.
            tok2 = self.tk.peek_token()
            if tok2.type == EToken.INTEGER:
                # Keep looking
                tok3 = self.tk.peek_token()
                if tok3.type == EToken.OBJECT_BEGIN:
                    # Start creating the object with the object number (from
                    # tok) and generation number (from tok2)
                    self.tk.next_token()  # peeked tok2
                    self.tk.next_token()  # peeked tok3
                    self.tok = self.tk.next_token()
                    obj = self.next_object()
                    return PdfObject(EObject.IND_OBJ_DEF,
                                     data=dict(obj=obj, objn=tok.data, gen=tok2.data))
                elif tok3.type == EToken.OBJ_REF:
                    self.tk.next_token()  # peeked tok2
                    self.tk.next_token()  # peeked tok3
                    self.tok = self.tk.next_token()
                    return PdfObject(EObject.IND_OBJ_REF,
                                     data=dict(objn=tok.data, gen=tok2.data))
            # Ignore tok2, we re-read it anyway
            self.tok = self.tk.next_token()
            return PdfObject(EObject.INTEGER, tok.data)

        # Is it a real number ?
        elif tok.type == EToken.REAL:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.REAL, tok.data)

        # Is it a string ?
        elif tok.type in [EToken.LITERAL_STRING, EToken.HEX_STRING]:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.STRING, tok.data)  # bytearray

        # Is it a name ?
        elif tok.type == EToken.NAME:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.NAME, tok.data)  # bytearray

        # Is it an array ?
        elif tok.type == EToken.ARRAY_BEGIN:
            # self.tok already has the right value, tok was taken from there
            obj = self.get_array()
            self.tok = self.tk.next_token()
            return obj

        # Is it a dictionary ?
        elif tok.type == EToken.DICT_BEGIN:
            # self.tok already has the right value, tok was taken from there
            obj = self.get_dictionary()
            self.tok = self.tk.next_token()
            return obj

        # Is it a stream ? FIXME

        # Is it null ?
        elif tok.type == EToken.NULL:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.NULL)

        # Nothing that was expected here
        else:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.ERROR)

#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    print('This module is not meant to be executed directly.')
