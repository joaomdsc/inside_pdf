#!/usr/bin/env python
# binfile.py - library to read binary files

import io
import os
import sys

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
# class BinFile
#-------------------------------------------------------------------------------

class BinFile:
    wspace = b'\0\t\n\f\r '
    delims = b'()<>[]{}/%'
    
    def __init__(self, filepath, blk_sz=io.DEFAULT_BUFFER_SIZE):
        self.filepath = filepath
        self.f = open(filepath, 'rb')
        self.blk_sz = blk_sz
        self.i = -1
        # Each block gets read into this buffer
        self.buf = b''
        self.buf_sz = 0
        # Peeking one byte might require looking ahead into a next block
        self.next_buf = b''

    def close(self):
        self.f.close()
        
    #---------------------------------------------------------------------------
    # next_byte
    #---------------------------------------------------------------------------
    
    def next_byte(self):
        """Get the next character from the file (including EOL's)."""
        self.i += 1
        if self.i == self.buf_sz:
            # Did we peek into the next block ?
            if self.next_buf:
                # self.buf has already been populated
                self.next_buf = b''
            else:
                self.buf = self.f.read(self.blk_sz)
            # Have we reached end-of-file ?
            if not self.buf:
                return -1

            self.buf_sz = len(self.buf)
            self.i = 0
        return self.buf[self.i]
        
    #---------------------------------------------------------------------------
    # peek_byte
    #---------------------------------------------------------------------------
    
    def peek_byte(self):
        """Have a peek at the next character from the file (including EOL's)."""
        j = self.i + 1
        if j == self.buf_sz:
            # Current buffer has been handled entirely, I don't need it anymore
            self.buf = self.next_buf = self.f.read(self.blk_sz)

            # Have we reached end-of-file ?
            if not self.buf:
                return -1

            # Don't change buf_sz here, we need the current value
            j = 0
        return self.buf[j]
    
#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    print('This module is not meant to be executed directly.')
