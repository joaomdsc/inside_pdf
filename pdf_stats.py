#!/usr/bin/env python
# pdf_stats.py - print out the pdf versions of every pdf file in a directory

import os
import re
import sys
from file_read_backwards import FileReadBackwards
from object_stream import EObject, XrefSection, ObjectStream

EOL = '(\r\n|\r|\n)'
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
# count_updates
#-------------------------------------------------------------------------------

# FIXME too long !!!
def count_updates(filepath):
    """Count the number of EOF markers."""
    cnt = 0
    with open(filepath, 'rb') as f:
        while True: 
            line = f.readline()
            if line == '':
                return cnt
            m = re.match(b'%%PDF' + bEOL, line)
            if m:
                cnt += 1

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
            print(f'"{filepath}" has no EOF marker')
            return trailer, offset

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

        # FIXME I'm not actually getting the trailer dictionary here. I could
        # (should ?) continue reading backwards until I find the 'trailer' and
        # '<<'. But the trailer dict can old other dicts... can I parse this
        # backwards ? I can't just look for the string 'trailer', it could be
        # in the value of any dictionary key inside the trailer dictionary.
            
    return trailer, offset

#-------------------------------------------------------------------------------
# deref_object - read an indirect object from the file
#-------------------------------------------------------------------------------

def deref_object(o, ob, xref_sec):
    # FIXME make this a method of ObjStream, perhaps ? to get the right context ?
    """Read a dictionary, return it as a python dict with PdfObject values."""
    if o.type != EObject.IND_OBJ_REF:
        print(f'Expecting an indirect object reference, got "{o.type}"'
              + ' instead')
        return None

    # Now use objn to search the xref table for the file offset where
    # this catalog dictionary object can be found; seek the file to
    # that offset, and do another ob.next_object()

    # print(f"Getting object referred to by {o.data['objn']} {o.data['gen']}")

    # Catalog dictionary object is found at this offset, go there
    entry = xref_sec.get_object(o.data['objn'], o.data['gen'])
    if not entry:
        return None
    offset, _, _ = entry
    ob.seek(offset)

    # Now read the next char, this will be the beginning of
    # "6082 0 obj^M<</Metadata 6125 0 R ..." where 6082 is the objn
    o = ob.next_object()
    if o.type != EObject.IND_OBJ_DEF:
        print(f'Expecting an indirect object definition, got "{o.type}"'
              + ' instead')
        return None

    # The indirect object definition surrounds the object we want
    return o.data['obj']

#-------------------------------------------------------------------------------
# get_xref - read file from the end, extract the xref table
#-------------------------------------------------------------------------------

def get_xref(filepath):
    """Extract the xref table that is found from the file trailer."""
    # This code does not support any context. It opens its own files, and
    # doesn't need to worry about returning a proper state.
    offset = -1
    trailer = False

    print(f'get_xref: filepath={filepath}')

    # "The line terminator is always b'\n' for binary files", so says the
    # Python Std Library doc. It's really not a good idea to use readline()

    with FileReadBackwards(filepath) as f:
        # Last line
        line = f.readline()
        m = re.match('%%EOF' + EOL, line)
        if not m:
            print('syntax error: no EOF marker at the end of file')

        # Byte offset of last cross-reference section
        line = f.readline().rstrip()
        offset = int(line)

    # Here I use a different strategy than the one discussed in get_trailer()
    # above: I use the offset information to jump to the beginning of the xref
    # table, parse the entire xref table, and then look for a trailer... except
    # that sometimes I don't find one :-(
    
    with open(filepath, 'rb') as f:
        ob = ObjectStream(filepath, f)
        ob.seek(offset)
        o = ob.get_xref_section()
        xref_sec = o.data

        # # Print out the cross reference table
        # print()
        # print('xref')
        # print(xref_sec)
        
        # What comes after the cross reference section ?
        trailer_follows = False
        o = ob.next_object()
        if o.type == EObject.TRAILER:
            # Trailer immediately follows xref
            trailer_follows = True

            # Now get the trailer dictionary
            o = o.data
            if o.type != EObject.DICTIONARY:
                print("Error: trailer doesn't have a dictionary")
                return (len(xref_sec.sub_sections), trailer_follows)

            # # Need to read the Prev key first, otherwise we don't have all the
            # # cross-references
            # prev = o.data['Prev']
            # if prev.type != EObject.IND_OBJ_REF:
            #     print('Syntax error, /Prev key should be an indirect reference')
            #     return (len(xref_section), trailer_follows)
            # prev_objn = prev.data['objn']
            # prev_gen = prev.data['gen']

            # What we're really interested in, is the catalog dictionary for
            # the PDF document, which is in the Root key
            # print(f'Accessing Root element in "{filepath}"')
            root = deref_object(o.data['Root'], ob, xref_sec)

            # d is a python dictionary, but the items are PdfObjects
            d = root.data
            print(f"Catalog dictionary: {filepath.split(';')[0]}")
            for k, v in d.items():
                print(f'    {k}: {v}')

            # Next we're interested in the Info dictionary
            info = deref_object(o.data['Info'], ob, xref_sec)

            # d is a python dictionary, but the items are PdfObjects
            d = info.data
            print(f"Information dictionary: {filepath.split(';')[0]}")
            for k, v in d.items():
                print(f'    {k}: {v}')

        return len(xref_sec.sub_sections), trailer_follows
        
#-------------------------------------------------------------------------------
# stats_file_to_csv
#-------------------------------------------------------------------------------

def stats_file_to_csv(filepath):
    # Get the filename
    filename = os.path.basename(filepath)
    
    # Get the file size
    statinfo = os.stat(filepath)
    sz = statinfo.st_size

    # Get other info
    eol = get_eol(filepath)
    major, minor = get_version(filepath)
    trailer, offset = get_trailer(filepath)
    # eofs = count_updates(filepath)
    nsubs, tfollows = get_xref(filepath)

    # # Print out one .csv line
    # s = (f'{filename};{major}.{minor};{eol:4}'
    #          + f';{"true" if trailer else "false"};{offset:8};{sz}')
    # print(s, end='')
    # if(nsubs == 0):
    #     s = ';ignored;ignored'
    # else:
    #     s = f';{nsubs};{"true" if tfollows else "false"}'
    # print(s)
            
        
#-------------------------------------------------------------------------------
# stats_dir_to_csv
#-------------------------------------------------------------------------------

def stats_dir_to_csv(path):
    print('Filename;Version;EOL;Trailer;Offset;FileSize;#SubSections;TFollows')
    for f in os.listdir(path):
        if f.endswith('.pdf'):
            filepath = os.path.join(path, f)
            stats_file_to_csv(filepath)


#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':

    # Check cmd line arguments
    if len(sys.argv) == 2:
        filepath = sys.argv[1]
        stats_file_to_csv(filepath)
    else:
        # My pdf file repository
        stats_dir_to_csv(r'C:\u\pdf')

        # # Print catalog dictionaries
        # with open('pdfs_simple.csv', 'r') as f:
        #     first = True
        #     for line in f:
        #         if first:
        #             first = False
        #             continue
        #         filename = line.split(';')[0]
        #         print(filename)
        #         filepath = os.path.join(r'C:\u\pdf', filename)
        #         stats_file_to_csv(filepath)
