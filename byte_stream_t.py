#!/usr/bin/env python
# byte_stream_t.py

import os
import unittest
import byte_stream

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

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

class ByteStreamTest(unittest.TestCase):
    """Test the parsing of binary files."""

    path = 't'

    def test01(self):
        """Test simple next_byte() calls, up to and across the block boundary."""
        filepath = r't\sample.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)
        
            cc = bf.next_byte()
            self.assertEqual(ord('0'), cc)
            cc = bf.next_byte()
            self.assertEqual(ord('1'), cc)
            cc = bf.next_byte()
            self.assertEqual(ord('2'), cc)

            # read up to and including the 'd'
            for k in range(11): cc = bf.next_byte()

            cc = bf.next_byte()
            self.assertEqual(ord('e'), cc)
            cc = bf.next_byte()
            self.assertEqual(ord('f'), cc)
            cc = bf.next_byte()
            self.assertEqual(ord('g'), cc)  # crossed the block border
            cc = bf.next_byte()
            self.assertEqual(ord('h'), cc)

    def test02(self):
        """Test next_byte(3) calls, up to and across the block boundary."""
        filepath = r't\sample.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)
        
            s = bf.next_byte(3)
            self.assertEqual(b'012', s)
            s = bf.next_byte(3)
            self.assertEqual(b'345', s)
            s = bf.next_byte(9)
            self.assertEqual(b'6789abcde', s)
            s = bf.next_byte(4)
            self.assertEqual(b'fghi', s)  # crossed the block border
            s = bf.next_byte(3)
            self.assertEqual(b'jkl', s)

    def test03(self):
        """Read some characters, seek back, read again.."""
        filepath = r't\sample.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            s = bf.next_byte(18)
            self.assertEqual(b'gh', s[16:])
            s = bf.next_byte(3)
            self.assertEqual(b'ijk', s)
            bf.seek(5)
            s = bf.next_byte(2)
            self.assertEqual(b'56', s)

    def test04(self):
        """Read some characters, seek back, read again.."""
        filepath = r't\sample.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            # Read some bytes
            s = bf.next_byte(8)
            self.assertEqual(b'01234567', s)

            # Memorize this position
            p = bf.tell()

            # Read more
            s = bf.next_byte(5)
            self.assertEqual(b'89abc', s)

            # Go back to memorized position
            bf.seek(p)
            s = bf.next_byte(2)
            self.assertEqual(b'89', s)
         
    def test05(self):
        """Read some characters, seek back, read again.."""
        filepath = r't\sample.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            # File holds 28 bytes of text + CRLF = 30
            s = bf.next_byte(31)
            self.assertEqual(-1, s)
         
    def test06(self):
        """Read some characters, use tell(), seek back, read again.."""
        filepath = r't\sample.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            s = bf.next_byte(4)
            self.assertEqual(b'0123', s)
            pos = bf.tell()
            s = bf.next_byte(5)
            self.assertEqual(b'45678', s)
            s = bf.next_byte(6)
            self.assertEqual(b'9abcde', s)

            bf.seek(pos)
            s = bf.next_byte(3)
            self.assertEqual(b'456', s)            
            s = bf.next_byte(10)
            self.assertEqual(b'789abcdefg', s)

            pos2 = bf.tell()

            bf.seek(pos)
            s = bf.next_byte(2)
            self.assertEqual(b'45', s)        

            bf.seek(pos2)
            s = bf.next_byte(4)
            self.assertEqual(b'hijk', s)        
         
    def test07(self):
        """Memorize starting position, read, go back."""
        filepath = r't\sample.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            pos = bf.tell()
            
            s = bf.next_byte(4)
            self.assertEqual(b'0123', s)
            s = bf.next_byte(5)
            self.assertEqual(b'45678', s)
            s = bf.next_byte(6)
            self.assertEqual(b'9abcde', s)

            pos2 = bf.tell()

            bf.seek(pos)  # Move back to 0
            
            s = bf.next_byte(4)
            self.assertEqual(b'0123', s)
            s = bf.next_byte(3)
            self.assertEqual(b'456', s)

            bf.seek(pos2)  # Move forward to 15
            
            s = bf.next_byte(2)
            self.assertEqual(b'fg', s)
            s = bf.next_byte(5)
            self.assertEqual(b'hijkl', s)
         
    def test08(self):
        """Same as test07, but get some bytes before the first tell()"""
        filepath = r't\sample.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)
            
            s = bf.next_byte(3)
            self.assertEqual(b'012', s)

            pos = bf.tell()
            
            s = bf.next_byte(5)
            self.assertEqual(b'34567', s)
            s = bf.next_byte(4)
            self.assertEqual(b'89ab', s)

            pos2 = bf.tell()

            bf.seek(pos)  # Move back to 3
            
            s = bf.next_byte(4)
            self.assertEqual(b'3456', s)
            s = bf.next_byte(3)
            self.assertEqual(b'789', s)

            bf.seek(pos2)  # Move forward to 12
            
            s = bf.next_byte(2)
            self.assertEqual(b'cd', s)
            s = bf.next_byte(5)
            self.assertEqual(b'efghi', s)
         
    def test09(self):
        """File holds several blocks"""
        filepath = r't\blocks.dat'
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)
            
            s = bf.next_byte(3)
            self.assertEqual(b'abc', s)

            pos = bf.tell()
            
            s = bf.next_byte(65)
            self.assertEqual(b'fgh', s[62:])
            s = bf.next_byte(4)
            self.assertEqual(b'ij01', s)
            
            pos2 = bf.tell()

            bf.seek(pos)  # Move back to 3

            s = bf.next_byte(5)
            self.assertEqual(b'defgh', s)
            
            bf.seek(pos2)  # Move forward to 72

            s = bf.next_byte(3)
            self.assertEqual(b'234', s)

if __name__ == '__main__':
    unittest.main(verbosity=2)

