#!/usr/bin/env python
# pdf_stats.py - print out the pdf versions of every pdf file in a directory

import os
import re
import sys
from file_read_backwards import FileReadBackwards
from object_stream import EObject, XrefSection, ObjectStream

EOL = '(\r\n|\r|\n)'
bEOL = b'(\r\n|\r|\n)'

#-------------------------------------------------------------------------------
# I want stdout to be unbuffered, always
#-------------------------------------------------------------------------------

# class Unbuffered(object):
#     def __init__(self, stream):
#         self.stream = stream
#     def write(self, data):
#         self.stream.write(data)
#         self.stream.flush()
#     def __getattr__(self, attr):
#         return getattr(self.stream, attr)

# import sys
# sys.stdout = Unbuffered(sys.stdout)

#-------------------------------------------------------------------------------
# Printing LF and not CRLF on stdout on Windows 
#-------------------------------------------------------------------------------

import sys
sys.stdout = open(sys.__stdout__.fileno(), 
              mode=sys.__stdout__.mode, 
              buffering=1, 
              encoding=sys.__stdout__.encoding, 
              errors=sys.__stdout__.errors, 
              newline='\n', 
              closefd=False)

# Force utf-8 output
sys.stdout.reconfigure(encoding='utf-8')
                
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
# get_file_data - read file from the end, extract xref table, trailer
#-------------------------------------------------------------------------------

def get_file_data(filepath):
    """Extract the xref table that is found from the file trailer."""
    # This code does not support any context. It opens its own files, and
    # doesn't need to worry about returning a proper state.
    offset = -1
    trailer = False

    print(f'get_file_data: filepath={filepath}')

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

        # PDF Spec, § 7.5.8 Cross-Reference Streams, page 49:
        
        # Beginning with PDF 1.5, cross-reference information may be stored in
        # a cross-reference stream instead of in a cross-reference table.
        # Cross-reference streams are stream objects (see 7.3.8, "Stream
        # Objects"), and contain a dictionary and a data stream.
        
        # The value following the startxref keyword shall be the offset of the
        # cross-reference stream rather than the xref keyword.

        ob.seek(offset)
        o = ob.get_cross_reference()
        if o.type == EObject.XREF_SECTION:
            print('traditional')
            xref_sec = o.data
        elif o.type == EObject.IND_OBJ_DEF:
            # o.data is a dictionary {'obj': xxx, 'objn': n, 'gen': m}
            print('modern')
            o = o.data['obj']  # COUPLE

            # The values of all entries [in the stream dictionary] shall be
            # direct objects; indirect references shall not be permitted. For
            # arrays (the Index and W entries), all of their elements shall be
            # direct objects as well. If the stream is encoded, the Filter and
            # DecodeParms entries in Table 5 shall also be direct objects.

            # Stream dictionary: all entries are direct objects
            print(o.data[0].show())
            d = o.data[0].data

            # Size is required
            sz = d['Size'].data

            # Index is optional, defaults to [0, sz]
            # FIXME there could be several subsections ?
            if 'Index' in d:
                arr = d['Index'].data
                if len(arr) > 2:
                    print('FIXME: more than one cross-reference table subsection')
                first_objn = arr[0]
                entry_cnt = arr[1]
            else:
                first_objn = 0
                entry_cnt = sz

            # Decoding parameters
            columns = None
            predictor = None
            if 'DecodeParms' in d:
                print("Decode params present:")
                dp = d['DecodeParms'].data
                if 'Columns' in dp:
                    columns = dp['Columns'].data
                if 'Predictor' in dp:
                    predictor = dp['Predictor'].data
            print(f'    columns={columns}\n    predictor={predictor}')
                    
            # W key holds an array of PdfObject INTEGER elements
            w = [x.data for x in d['W'].data]
            
            # Show decoded stream
            s = o.data[1].data
            print(f'Compressed data stream length = {len(s)}'
                  + f", /Length={d['Length'].data}")
            p, x = ob.deflate_stream(s, columns, predictor, w)
            if p:
                xref_sec = XrefSection()
                arr = x
                # This a cross-reference sub-section
                subs = XrefSubSection(first_objn, entry_cnt)
                for t in arr:
                    # FIXME there are type 2 entries
                    subs.entries.append(t)
                # FIXME more than one subsection ?
                xref_sec.sub_sections.append(subs)
                return 1, False
            else:
                zd = x
                print(f'Uncompressed data stream length = {len(zd)}')
                # print(zd)
            return 0, False

        # # Print out the cross reference table
        print(o.show())
        # print(xref_sec)
        
        # What comes after the cross reference section ?
        trailer_follows = False
        o = ob.next_object()
        if o.type == EObject.TRAILER:
            # Trailer immediately follows xref
            print(o.show())
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

            # The Root key holds the catalog dictionary for the PDF
            # document. It's a required key, and it's an indirect reference.
            root = ob.deref_object(o.data['Root'])

            if root:
                # d is a python dictionary, but the items are PdfObjects
                d = root.data
                print(f"Catalog dictionary: {filepath.split(';')[0]}")
                for k, v in d.items():
                    print(f'    {k}: {v.show()}')
            else:
                print(f'Root is an indirect reference, not found in xref table')

            # The Info key, if present, holds the information dictionary.
            if 'Info' in o.data:
                info = ob.deref_object(o.data['Info'])

                if info:
                    # d is a python dictionary, but the items are PdfObjects
                    d = info.data
                    print(f"Information dictionary: {filepath.split(';')[0]}")
                    for k, v in d.items():
                        print(f'    {k}: {v.show()}')

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
    nsubs, tfollows = get_file_data(filepath)

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
