#!/usr/bin/env python
# byte_stream.py - read a stream of bytes from a binary file

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
# class ByteStream
#-------------------------------------------------------------------------------

class ByteStream:
    
    def __init__(self, filepath, f, blk_sz=io.DEFAULT_BUFFER_SIZE):
        self.filepath = filepath
        self.f = f
        self.blk_sz = blk_sz
        
        self.buf = b''  # normal
        self.i = 0
        self.peek_ahead = False
        self.next_buf = b''  # when peek_ahead is True, use this as data source

    def reset(self, offset):
        self.f.seek(offset)
        # Normal init
        self.buf = b''  # normal
        self.i = 0
        self.peek_ahead = False
        self.next_buf = b''  # when peek_ahead is True, use this as data source
        

    def close(self):
        self.f.close()
        
    #---------------------------------------------------------------------------
    # next_byte
    #---------------------------------------------------------------------------
    
    def next_byte(self, n=1):
        """Get the next character from the file, checking next_buf as needed."""
        s = bytearray(b'')
        for k in range(n):
            # Have we reached the end of the current buffer ?
            if self.i == len(self.buf):
                # if peek_ahead is True, get next_buf, otherwise read a new one
                if self.peek_ahead == True:
                    self.peek_ahead = False
                    self.buf = self.next_buf
                    self.next_buf = b''
                else:
                    self.buf = self.f.read(self.blk_sz)
                    if not self.buf:
                        return -1                

                # Reset the index
                self.i = 0
            s.append(self.buf[self.i])
            self.i += 1
        if n == 1:
            return s[0]
        return s
        
    #---------------------------------------------------------------------------
    # peek_byte
    #---------------------------------------------------------------------------
    
    def peek_byte(self, n=1):
        """Have a peek at the next character(s) from the file. Read a new buffer if needed.
"""
        # peek() always starts out from the next() state
        peek_buf = self.buf
        j = self.i
        
        s = bytearray(b'')
        for k in range(n):
            if j == len(peek_buf):
                # self.buf has been exhausted by peek, need to move to the next
                # block, do I have it already ?
                if not self.peek_ahead:
                    # Read a new block from file
                    self.peek_ahead = True
                    self.next_buf = self.f.read(self.blk_sz)
                    if not self.next_buf:
                        return -1
                peek_buf = self.next_buf

                # Reset the index
                j = 0
            # I should be getting chars from next_buf now
            s.append(peek_buf[j])
            j += 1
        if n == 1:
            return s[0]
        return s
            
    #---------------------------------------------------------------------------
    # next_stream
    #---------------------------------------------------------------------------
    
    def next_stream(self, length):
        """Get the next stream of 'length' bytes from the file."""

        # If a next block has already been read from the file (after peeking
        # beyong the current buffer) we ignore that, it will be read again.
        self.peek_ahead = False
        self.next_buf = b''

        # Number of bytes available in the current buffer
        available = len(self.buf) - self.i

        # Can we serve this request entirely form the current buffer ?
        if length <= available:
            s = self.buf[self.i:self.i + length]
            self.i += length
            return s

        # We need more then one block 
        s = bytearray(b'')
        s += self.buf[self.i:]
        remaining = length - available
        while True:
           x = self.f.read(self.blk_sz)
           if not x:
               # We may have read part of the stream, but we don't return that 
               return -1
           # Is this the last block we need to read ? 
           if remaining <= len(x):
               s += x[:remaining]
               # This self.buf has an unusual length, but it doesn't matter
               self.buf = x[remaining:]
               self.i = 0
               return s
           s += x
           remaining -= len(x)

#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    print('This module is not meant to be executed directly.')
