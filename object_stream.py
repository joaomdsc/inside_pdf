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
    ERROR = auto()          # pseudo-object describing a parsing error 
    EOF = auto()            # pseudo-object describing the EOF condition
    VERSION_MARKER = auto() # %PDF-n.m
    EOF_MARKER = auto()     # %%EOF
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
    TRAILER = auto()        # file trailer
    STARTXREF = auto()      # the 'startxref' keyword
    STREAM_DATA = auto()    # the bytes between 'stream' and 'endstream'
    COUPLE = auto()         # a couple of objetcs, such as (dict, stream)

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
                # s += f"({k}, {v.data.decode('unicode_escape')}, "
                
                # Dictionary values can be any kind of PdfObject, I need a real
                # recursive object-printing function.
                s += f"({k},) "
            s += '}'
        elif self.type == EObject.XREF_SECTION:
            xref_sec = self.data
            s += f'{len(xref_sec.sub_sections)}'
        elif self.type == EObject.TRAILER:
            s += f'{self.data}'
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

    def seek(self, offset):
        self.tk.seek(offset)
        # Normal init
        self.tok = self.tk.next_token()
      
    #---------------------------------------------------------------------------
    # get_indirect_obj_def
    #---------------------------------------------------------------------------
 
    def get_indirect_obj_def(self):
        """Found the opening OBJECT_BEGIN token, now get the entire object."""
        # self.tok has an EToken.OBJECT_BEGIN, parse the following tokens.
        # Return is done with the closing token (already analyzed) in self.tok.
        tok = self.tok

        # Get the defined (internal) object
        self.tok = self.tk.next_token()
        if tok.type == EToken.EOF:
            return PdfObject(EObject.EOF)
        elif tok.type == EToken.ERROR:
            return PdfObject(EObject.ERROR)

        # Get the defined (internal) object
        obj = self.next_object()
        if obj.type in [EObject.ERROR, EObject.EOF]:
            return obj
        
        # self.tok holds the next token, read but not yet analyzed
        tok = self.tok

        # Ignore any end-if-line marker
        if tok.type in [EToken.CR, EToken.LF, EToken.CRLF]:
            tok = self.tk.next_token()
            if tok.type == EToken.EOF:
                return PdfObject(EObject.EOF)
            elif tok.type == EToken.ERROR:
                return PdfObject(EObject.ERROR)
            
        if tok.type == EToken.OBJECT_END:
            return obj
      
    #---------------------------------------------------------------------------
    # get_array
    #---------------------------------------------------------------------------
 
    def get_array(self):
        """Found the opening ARRAY_BEGIN token, now get the entire array."""
        # self.tok has an EToken.ARRAY_BEGIN, parse the following tokens.
        # Return is done with the closing token (already analyzed) in self.tok.

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
            if obj.type in [EObject.ERROR, EObject.EOF]:
                return obj
            
            # self.tok holds the next token, read but not yet analyzed
            tok = self.tok

            arr.append(obj)
      
    #---------------------------------------------------------------------------
    # get_dictionary
    #---------------------------------------------------------------------------
 
    def get_dictionary(self):
        """Found the opening DICT_BEGIN token, now get the entire dictionary."""
        # self.tok has an EToken.DICT_BEGIN, parse the following tokens.
        # Return is done with the closing token (already analyzed) in self.tok.

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
    # get_stream
    #---------------------------------------------------------------------------
 
    def get_stream(self, length):
        """Found the opening STREAM_BEGIN token, now get the entire dictionary."""
        # self.tok has an EToken.STREAM_BEGIN, parse the following tokens.
        # Return is done with the closing token (already analyzed) in self.tok.

        # FIXME better to ask for forgiveness than for permission. I need to
        # stop testing EOF and ERROR and every single next_XXX() function, use
        # exceptions instead.

        # Get the token that follows 'stream' (CRLF or LF)
        tok = self.tk.next_token()
        if tok.type == EToken.EOF:
            return PdfObject(EObject.EOF)

        # "The keyword stream that follows the stream dictionary shall be
        # followed by an end-of-line marker consisting of either a CARRIAGE
        # RETURN and a LINE FEED or just a LINE FEED, and not by a CARRIAGE
        # RETURN alone". PDF spec, § 7.3.8.1, page 19
        if tok.type not in [EToken.LF, EToken.CRLF]:
            return PdfObject(EObject.ERROR)

        # Get the token with the stream data
        tok = self.tk.next_stream(length)
        if tok.type == EToken.EOF:
            return PdfObject(EObject.EOF)

        # "There should be an end-of-line marker after the data and before
        # endstream; this marker shall not be included in the stream length".
        # PDF spec, § 7.3.8.1, page 19
        tok = self.tk.next_token()
        if tok.type == EToken.EOF:
            return PdfObject(EObject.EOF)
        if tok.type not in [EToken.CR, EToken.LF, EToken.CRLF]:
            return PdfObject(EObject.ERROR)

        # Get the closing STREAM_END
        tok = self.tk.next_token()
        if tok.type == EToken.EOF:
            return PdfObject(EObject.EOF)
        if tok.type != EToken.STREAM_END:
            return PdfObject(EObject.ERROR)

        # Return the stream data object, with the closing _END token 
        return PdfObject(EObject.STREAM_DATA, data=tok.data)


    #---------------------------------------------------------------------------
    # get_xref_section
    #---------------------------------------------------------------------------

    def get_xref_section(self):
        """Parse a cross reference section into an object"""
        # self.tok has a EToken.XREF_SECTION, parse the following tokens.

        # "Each cross-reference section shall begin with a line containing the
        # keyword xref": this implies an end-of-line marker after 'xref'
        tok = self.tk.next_token()
        if tok.type not in [EToken.CR, EToken.LF, EToken.CRLF]:
            self.tok = tok  # FIXME this way, self.tok will be analyzed again
            return PdfObject(EObject.ERROR)

        # Loop over cross-reference subsections
        xref_sec = XrefSection()
        while True:
            # Get a special token representing the sub-section header
            tok = self.tk.get_subsection_header()
            if tok.type == EToken.EOF:
                return PdfObject(EObject.EOF)
            if tok.type == EToken.ERROR:
                return PdfObject(EObject.ERROR)
            if tok.type == EToken.UNEXPECTED:
                # Couldn't parse the line as a sub-section header, this means
                # that the sub-section is over.
                self.xref_sec = xref_sec
                
                # State has been rolled back, so prepare to continue
                self.tok = self.tk.next_token()
                return PdfObject(EObject.XREF_SECTION, xref_sec)

            # Sub-section header was successfully parsed
            first_objn, entry_cnt = tok.data

            # I'm assuming entry_cnt is not 0.
            subs = XrefSubSection(first_objn, entry_cnt)
            for i in range(entry_cnt):
                # Get a special token representing a sub-section entry
                tok = self.tk.get_subsection_entry()
                if tok.type == EToken.EOF:
                    return PdfObject(EObject.EOF)
                if tok.type == EToken.ERROR:
                    return PdfObject(EObject.ERROR)
                subs.entries.append(tok.data)

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
                    # Get the defined (internal) object
                    self.tok = tok3
                    obj = self.get_indirect_obj_def()
                    if obj.type in [EObject.ERROR, EObject.EOF]:
                        return obj
                    self.tok = self.tk.next_token()
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
            if obj.type in [EObject.ERROR, EObject.EOF]:
                return obj
            self.tok = self.tk.next_token()
            return obj

        # Is it a dictionary ? or a (dictionary, stream) couple ?
        elif tok.type == EToken.DICT_BEGIN:
            # self.tok already has the right value, tok was taken from there
            obj = self.get_dictionary()  # self.tok == DICT_END
            if obj.type in [EObject.ERROR, EObject.EOF]:
                return obj
            while True:
                self.tok = self.tk.next_token()
                if self.tok not in [EToken.CR, EToken.LF, EToken.CRLF]:
                    break
            if self.tok.type != EToken.STREAM_BEGIN:
                return obj  # return the dict

            # We have found a STREAM_BEGIN token, the 'obj' dict has the Length
            d = obj.data
            obj2 = self.get_stream(d['Length'].data)
            # FIXME ask for forgiveness, not permission 
            if obj2.type in [EObject.ERROR, EObject.EOF]:
                return obj2
            self.tok = self.tk.next_token()
            return PdfObject(EObject.COUPLE, data=(obj, obj2))

        # Is it a xref section ?
        elif tok.type == EToken.XREF_SECTION:
            obj = self.get_xref_section()
            # self.tok already holds the next token
            return obj

        # Is it a trailer ?
        elif tok.type == EToken.TRAILER:
            tok = self.tk.next_token()
            # Ignore CRLF (why do I parse the tokens then ?)
            while tok.type in [EToken.CR, EToken.LF, EToken.CRLF]:
                tok = self.tk.next_token()
            if tok.type != EToken.DICT_BEGIN:
                # FIXME specify once and for all which token I want to see when
                # an error has been detected. The question is "how do I recover
                # from this error ?"
                self.tok = self.tk.next_token()
                return PdfObject(EObject.ERROR)
            obj = self.get_dictionary()
            self.tok = self.tk.next_token()
            return PdfObject(EObject.TRAILER, obj)

        elif tok.type == EToken.STARTXREF:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.STARTXREF)

        elif tok.type == EToken.EOF_MARKER:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.EOF_MARKER)

        # Is it a stream ? FIXME
        elif tok.type == EToken.STREAM_BEGIN:
            sys.exit()

        # Is it null ?
        elif tok.type == EToken.NULL:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.NULL)

        # Nothing that was expected here
        else:
            self.tok = self.tk.next_token()
            return PdfObject(EObject.ERROR)

    #---------------------------------------------------------------------------
    # deref_object - read an indirect object from the file
    #---------------------------------------------------------------------------

    def deref_object(self, o):
        """Read a dictionary, return it as a python dict with PdfObject values."""
        if o.type != EObject.IND_OBJ_REF:
            print(f'Expecting an indirect object reference, got "{o.type}"'
                  + ' instead')
            return None

        if not self.xref_sec:
            return None

        # Now use objn to search the xref table for the file offset where
        # this catalog dictionary object can be found; seek the file to
        # that offset, and do another ob.next_object()

        # Catalog dictionary object is found at this offset, go there
        entry = self.xref_sec.get_object(o.data['objn'], o.data['gen'])
        if not entry:
            return None
        offset, _, _ = entry
        self.seek(offset)

        # Now read the next char, this will be the beginning of
        # "6082 0 obj^M<</Metadata 6125 0 R ..." where 6082 is the objn
        o = self.next_object()
        if o.type != EObject.IND_OBJ_DEF:
            print(f'Expecting an indirect object definition, got "{o.type}"'
                  + ' instead')
            return None

        # The indirect object definition surrounds the object we want
        return o.data['obj']

#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    print('This module is not meant to be executed directly.')
