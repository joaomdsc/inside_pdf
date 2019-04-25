#!/usr/bin/env python
# pdf_stats.py - print out the pdf versions of every pdf file in a directory

import os
import re
import sys
from file_read_backwards import FileReadBackwards
import binfile
from objects import ObjStream, EObject

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
# XrefSubSection - represent a sub-section of a cross-reference table
#-------------------------------------------------------------------------------

class XrefSubSection:
    """Represent a sub-section of a xref section."""
    def __init__(self, objn, entry_cnt):
        self.objn = objn
        self.entry_cnt = entry_cnt
        self.entries = []  # each entry is a 4-tuple (objn, x, gen, in_use)

    def has_objn(self, n):
        return self.objn <= n < self.objn + self.entry_cnt

    def get_object(self, n)
        if self.has_objn(n);
            return self.entries[n - self.objn]
        else:
            return None

#-------------------------------------------------------------------------------
# XrefSection - represent a cross-reference section
#-------------------------------------------------------------------------------

# The xref table comprises one or more cross-reference sections

class XrefSection:
    """Represent a cross-reference section in a PDF file xref table."""
    def __init__(self):
        # Sub-sections are not sorted
        self.sub_sections = []

    # FIXME code a functional version of this
    def get_object(self, n)
        for subs in self.sub_sections:
            o = subs.get_object(n)
            if o:
                return o
        return None

#-------------------------------------------------------------------------------
# get_xref - read file from the end, extract the xref table
#-------------------------------------------------------------------------------

def get_xref(filepath):
    """Extract the xref table."""
    offset = -1
    trailer = False

    # print(f'get_xref: filepath={filepath}')
    
    with FileReadBackwards(filepath) as f:
        # Last line
        line = f.readline()
        m = re.match('%%EOF' + EOL, line)
        if not m:
            print('syntax error: no EOF marker')

        # Byte offset of last cross-reference section
        line = f.readline().rstrip()
        offset = int(line)

    with open(filepath, 'rb') as f:
        f.seek(offset)
        line = f.readline()
        m = re.match(b'xref' + bEOL, line)
        if not m:
            # ignoring file: xref not found where expected from offset
            return 0, False

        # Loop over cross-reference subsections
        xref_sec = XrefSection()
        while True:
            line = f.readline()
            if line == b'':
                break
            # print(f'line={line}')
            m = re.match(b'(\d+) (\d+)' + bEOL, line)
            if not m:
                # No more sub-sections, but what is in 'line' ? Don't know yet
                break

            # Each cross-reference subsection shall contain entries for a
            # contiguous range of object numbers.
            objn = first_obj_nbr = int(m.group(1))
            entry_cnt = int(m.group(2))  # I'm assuming entry_cnt is not 0.

            subs = XrefSubSection(objn, entry_cnt)
            for i in range(entry_cnt):
                line = f.readline()
                pat = b'(\d{10}) (\d{5}) ([nf])' + bEOLSP
                m = re.match(pat, line)
                if not m:
                    # I know the entry count, this should never happen
                    raise ValueError(f'Fatal error: found "{line}" instead of a xref entry')
                x = int(m.group(1))  # offset, if in_use, or object number if free
                gen = int(m.group(2))
                in_use = m.group(3) == 'n'
                subs.entries.append((objn, x, gen, in_use))
                objn += 1
            # Finish off the this sub-section
            xref_sec.sub_sections.append(subs)

        # We've read some data into 'line', it's neither a sub-section header,
        # nor a xref entry. Need to analyze it further.
        trailer_follows = False
        m = re.match(b'trailer' + bEOL, line)
        if m:
            # Trailer immediately follows xref
            trailer_follows = True
            # FIXME there might be stuff between 'trailer' and the end of line

            # We now expect the trailer dictionary
            ob = ObjStream(filepath, f)
            o = ob.next_object()
            if o.type != EObject.DICTIONARY:
                print('Syntax error, incorrect trailer dict')
                return (len(xref_section), trailer_follows)

            # What we're really interested in, is the catalog dictionary for
            # the PDF document, which is in the Root key
            root = o.data['Root']
            if root.type != EObject.IND_OBJ_REF:
                print('Syntax error, /Root key should be an indirect reference')
                return (len(xref_section), trailer_follows)
            objn = root.data['objn']
            gen = root.data['gen']
            print(f'The catalog dictionary is in object {objn} {gen}')

            # Now use objn to search the xref table for the file offset where
            # this catalog dictionary object can be found; seek the file to
            # that offset, and do another ob.next_object()

            # FIXME Use 'gen' as well
            (objn, offset, gen, in_use) = xref_sec.get_object(objn)
             if not in_use:
                 print('oops: catalog dictionary object is a free entry ?!')
                 return len(xref_sec), trailer_follows

             print('File offset where the catalog dictionary object')
             # Get the actual object 
             f.seek(offset)
             # Now read the next char, this will be the beginning of
             # "6082 0 obj

             # FIXME I need to re-think the entire ObjStream / Tokener /
             # BinFile stack, so that I can do a seek() at the character level,
             # and from there start doing an ob.next_object()

        # # Print out what we found
        # for s in xref_section:
        #     for e in sub_section:
        #         (objn, x, gen, in_use) = e
        #         print(f'{objn}, {x}, {gen}, {in_use}')
        #     print()

        return len(xref_sec), trailer_follows
        
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
    s = (f'{filename};{major}.{minor};{eol:4}'
             + f';{"true" if trailer else "false"};{offset:8};{sz}')
    print(s, end='')
    if(nsubs == 0):
        s = ';ignored;ignored'
    else:
        s = f';{nsubs};{"true" if tfollows else "false"}'
    print(s)
            
        
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