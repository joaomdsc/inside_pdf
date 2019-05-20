#!/usr/bin/env python
# byte_stream.py - read a stream of bytes from a binary file

# Is this module useless?  I coded this to have read, tell, and seek when
# reading blocks of text at once.  Isn't this offered by the base modules?
# I should perform a comparison against the base modules.

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
        # Normal init
        self.buf = b''
        self.pos = 0
        self.s_pos = 0  # stream position (a.k.a. file pointer)

    # self.pos holds the (zero-based) index of the *next* character to be read.
    
    # self.s_pos (and the offset parameter to seek()) works like pos, it is
    # zero-based, and it points to the *next* byte that will be read.

    def seek(self, offset):
        self.f.seek(offset)
        # Normal init
        self.buf = b''
        self.pos = 0
        self.s_pos = offset

    def tell(self):
        # Why not self.f.tell() ? Because the file is read in blocks (usually
        # 8kb), the file level does not know what particular byte we're reading.
        return self.s_pos
        
    def close(self):
        self.f.close()

    # New functionality and interface: forget about peeking. Implement proper
    # tell() and seek() functions in next_byte, and that's it. Want to back out
    # at some point ? Assuming you called tell() at the right moment, just
    # seek() back to it. Much simpler.
        
    #---------------------------------------------------------------------------
    # next_byte
    #---------------------------------------------------------------------------
    
    def next_byte(self, n=1):
        """Get the next stream of 'n' bytes from the file."""

        # Number of bytes available in the current buffer
        available = len(self.buf) - self.pos

        # Have we reached the end of the current buffer ?
        if available == 0:
            # read a new buffer
            self.buf = self.f.read(self.blk_sz)
            if not self.buf:
                return -1
            # Reset the indexes
            available = len(self.buf)
            self.pos = 0

        # Can we serve this request entirely form the current buffer ?
        if n <= available:
            s = self.buf[self.pos:self.pos + n]
            self.pos += n
            self.s_pos += n
            if n == 1:
                return s[0]
            return s

        # We need more then one block 
        s = bytearray(b'')
        s += self.buf[self.pos:]
        remaining = n - available
        while True:
           x = self.f.read(self.blk_sz)
           if not x:
               # We may have read part of the stream, but we don't return that 
               self.s_pos = -1
               return -1
           # Is this the last block we need to read ? 
           if remaining <= len(x):
               s += x[:remaining]
               # This self.buf has an unusual n, but it doesn't matter
               self.buf = x[remaining:]
               self.pos = 0
               self.s_pos += n
               return s
           s += x
           remaining -= len(x)

#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
            
if __name__ == '__main__':
    print('This module is not meant to be executed directly.')
