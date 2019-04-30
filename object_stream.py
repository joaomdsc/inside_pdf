#!/usr/bin/env python
# object_stream.py - parse a stream of PDF spec objects from a stream of tokens

import os
import re
import sys
from enum import Enum, auto, unique
from token_stream import EToken, TokenStream

bEOL = b'(\r\n|\r|\n)'
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
#  EObject
#-------------------------------------------------------------------------------

# Possible object types in PDF files
@unique
class EObject(Enum):
    ERROR = auto()          # pseudo-object describing a parsing error 
    EOF = auto()            # pseudo-object describing the EOF condition
    VERSION_MARKER = auto() # %PDF-n.m
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
    XREF_SECTION = auto()   # cross reference section

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
        elif self.type == EObject.IND_OBJ_DEF:
            s += f"{self.data['objn']} {self.data['gen']} {self.data['obj']}"
        elif self.type == EObject.IND_OBJ_REF:
            s += f"{self.data['objn']} {self.data['gen']} R"
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
        elif self.type == EObject.XREF_SECTION:
            xref_sec = self.data
            s += f'{len(xref_sec.sub_sections)}'
        elif self.type == EObject.VERSION_MARKER:
            s += f'{self.data}'
        s += ')'
        return s

#-------------------------------------------------------------------------------
# class XrefSubSection - represent a sub-section of a cross-reference table
#-------------------------------------------------------------------------------

class XrefSubSection:
    """Represent a sub-section of a xref section."""
    def __init__(self, first_objn, entry_cnt):
        self.first_objn = first_objn
        self.entry_cnt = entry_cnt
        self.entries = []  # each entry is a 3-tuple (x, gen, in_use)

    def has_object(self, objn, gen):
        return self.first_objn <= objn < self.first_objn + self.entry_cnt

    def get_object(self, objn, gen):
        if self.has_object(objn, gen):
            return self.entries[objn - self.first_objn]
        else:
            return None

    def __str__(self):
        s = f'{self.first_objn} {self.entry_cnt}\n'
        for (x, gen, in_use) in self.entries:
            s += f'{x} {gen} {in_use}\n'
        return s

#-------------------------------------------------------------------------------
# class XrefSection - represent a cross-reference section
#-------------------------------------------------------------------------------

# The xref table comprises one or more cross-reference sections

class XrefSection:
    """Represent a cross-reference section in a PDF file xref table."""
    def __init__(self):
        # Sub-sections are not sorted
        self.sub_sections = []

    # FIXME code a functional version of this
    def get_object(self, objn, gen):
        for subs in self.sub_sections:
            # Return the first not None, or loop to the end
            o = subs.get_object(objn, gen)
            if o:
                return o
        return None

    def __str__(self):
        s = ''
        for subs in self.sub_sections:
            s += str(subs)
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

        # The xref table will be a property of the object stream ?

    def reset(self, offset):
        self.tk.reset(offset)
        # Normal init
        self.tok = self.tk.next_token()
      
    #---------------------------------------------------------------------------
    # get_indirect_obj_def
    #---------------------------------------------------------------------------
 
    def get_indirect_obj_def(self):
        """Found the opening OBJECT_BEGIN token, now get the entire object."""

        tok = self.tok
        obj = self.next_object()
        tok = self.tok
        if tok.type in [EToken.CR, EToken.LF, EToken.CRLF]:
            # Ignore end-if-line markers
            tok = self.tk.next_token()
        if tok.type == EToken.OBJECT_END:
            return obj
        elif tok.type == EToken.EOF:
            return PdfObject(EObject.EOF)
        else:
            return PdfObject(EObject.ERROR)
      
    #---------------------------------------------------------------------------
    # get_array
    #---------------------------------------------------------------------------
 
    def get_array(self):
        """Found the opening ARRAY_BEGIN token, now get the entire array."""
        # self.tok has a EToken.ARRAY_BEGIN, parse the following tokens.
        # Arrays can hold any kind of objects, including other arrays and
        # dictionaries.

        # Prepare an array object
        arr = []

        # FIXME shouldn't I ignore end-of-line characters ?

        tok = self.tk.next_token()
        while True:
            if tok.type == EToken.ARRAY_END:
                # It's a python array, but the elements are PdfObjects
                return PdfObject(EObject.ARRAY, arr)
            if tok.type == EToken.ERROR:
                return PdfObject(EObject.ERROR)
            if tok.type == EToken.EOF:
                return PdfObject(EObject.EOF)
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
        # self.tok has a EToken.DICT_BEGIN, parse the following tokens.
        # Dictionaries are sets of (key, value) pairs, where the value can be
        # any kind of object, including arrays and other dictionaries.

        # Prepare a dictionary object
        d = {}

        tok = self.tk.next_token()
        while True:
            if tok.type == EToken.DICT_END:
                # It's a python dictionary, but the values are PdfObjects
                return PdfObject(EObject.DICTIONARY, d)
            if tok.type == EToken.ERROR:
                return PdfObject(EObject.ERROR)
            if tok.type == EToken.EOF:
                return PdfObject(EObject.EOF)
            # Ignore end-if-line markers
            if tok.type in [EToken.CR, EToken.LF, EToken.CRLF]:
                tok = self.tk.next_token()
            elif tok.type == EToken.NAME:
                tok2 = self.tk.next_token()
                self.tok = tok2
                obj = self.next_object()
                # FIXME: can any bytes object be decoded like this ?
                # FIXME: I've lost the keys' original bytes object
                d[tok.data.decode('unicode_escape')] = obj            

                # The next token is already stored in self.tok, but it hasn't
                # been analyzed yet.
                tok = self.tok
            else:
                return PdfObject(EObject.ERROR)

    #---------------------------------------------------------------------------
    # get_xref_section - when we are given its offset in the file
    #---------------------------------------------------------------------------
    # There are two types of xref sections that may be found in a pdf file, and
    # two ways of finding them:
    #
    #   - read from the end, got to offset, find either the 'xref' keyword, or
    #     an object definition (which denotes a xref stream)
    #
    #   - parse the file sequentially, get a 'xref' token or object definition.
    #     This what is implemented below.
    #---------------------------------------------------------------------------

    def get_xref_section(self):
        """Parse a cross reference section into an object"""
        # self.tok has a EToken.XREF_SECTION, parse the following tokens.
        tok = self.tk.next_token()

        # Ignore end-if-line markers
        if tok.type in [EToken.CR, EToken.LF, EToken.CRLF]:
            # Don't do this... next_token() will return an INTEGER because it
            # lacks the context
            tok = self.tk.next_token()
            
        # Loop over cross-reference subsections
        xref_sec = XrefSection()
        while True:
            # "The line terminator is always b'\n' for binary files", so says
            # the Python Std Library doc. So it's not safe to use readline().
            line = self.f.readline()

            # I have 2 things to fix: need to implement my own tell() (and
            # rename reset() as seek(), btw); need to read these lines with my
            # token_/byte_stream stack.
            if line == b'':
                return PdfObject(EObject.EOF)

            # Each cross-reference subsection shall contain entries for a
            # contiguous range of object numbers. The subsection shall begin
            # with a line containing two numbers separated by a SPACE (20h),
            # denoting the object number of the first object in this subsection
            # and the number of entries in the subsection.
            # Ask the token_stream module for this information
            tok = self.tk.get_subsection_header()
            if tok.type == EToken.ERROR:
                return PdfObject(EObject.ERROR)
            if tok.type == EToken.EOF:
                return PdfObject(EObject.EOF)
            if not m:
                # We're returning here because we found a line that doesn't
                # match the beginning of a xref sub-section (this is the
                # equivalent of finding a _END token). We undo the last
                # readline so we can resume parsing normally.
                self.xref_sec = xref_sec
                self.reset(fpos)
                print(xref_sec)
                return PdfObject(EObject.XREF_SECTION, xref_sec)
            first_objn = int(m.group(1))
            entry_cnt = int(m.group(2))

            # I'm assuming entry_cnt is not 0.
            subs = XrefSubSection(first_objn, entry_cnt)
            for i in range(entry_cnt):
                fpos = self.f.tell()
                line = self.f.readline()
                pat = b'(\d{10}) (\d{5}) ([nf])' + bEOLSP
                m = re.match(pat, line)
                if not m:
                    # I know the entry count, this should never happen
                    return PdfObject(EObject.ERROR)
                x = int(m.group(1))  # offset, if in_use, or object number if free
                gen = int(m.group(2))
                in_use = m.group(3) == b'n'
                subs.entries.append((x, gen, in_use))
            # Finish off the this sub-section
            xref_sec.sub_sections.append(subs)
      
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
        elif tok.type == EToken.VERSION_MARKER:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.VERSION_MARKER, data=tok.data)

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
                    # This does not work, I miss the endobj keyword. I do get
                    # the next object - say, a dictionary - but that can be
                    # followed by an end of line and the endobj keyword.
                    obj = self.get_indirect_obj_def()
                    if obj.type in [EObject.ERROR, EObject.EOF]:
                        return obj
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

        # Is it a xref section ?
        elif tok.type == EToken.XREF_SECTION:
            obj = self.get_xref_section()
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
