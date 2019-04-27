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

    path = r'D:\joao\src\py\pdf\t'

    def test01(self):
        """Test simple next_byte() calls, up to and across the block boundary."""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
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
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
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
        """Test only peek() within the first block."""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            cc2 = bf.peek_byte()
            self.assertEqual(ord('0'), cc2)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('0'), cc2)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('0'), cc2)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('0'), cc2)

            s = bf.peek_byte(3)
            self.assertEqual(b'012', s)
            s = bf.peek_byte(3)
            self.assertEqual(b'012', s)
            s = bf.peek_byte(3)
            self.assertEqual(b'012', s)

    def test04(self):
        """Test peek() up to 15 caracters (mustn't exceed block size)."""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            s = bf.peek_byte(3)
            self.assertEqual(b'012', s)
            s = bf.peek_byte(6)
            self.assertEqual(b'012345', s)
            s = bf.peek_byte(9)
            self.assertEqual(b'012345678', s)
            s = bf.peek_byte(12)
            self.assertEqual(b'0123456789ab', s)
            s = bf.peek_byte(15)
            self.assertEqual(b'0123456789abcde', s)

    def test05(self):
        """Peek() first, then next(), mix them up."""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)
        
            cc2 = bf.peek_byte()
            self.assertEqual(ord('0'), cc2)

            cc = bf.next_byte()
            self.assertEqual(ord('0'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('1'), cc2)

            for i in range(13): cc = bf.next_byte()

            # Next byte has index 14
            cc = bf.next_byte()
            self.assertEqual(ord('e'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('f'), cc2)

            cc = bf.next_byte()
            self.assertEqual(ord('f'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('g'), cc2)

            cc = bf.next_byte()
            self.assertEqual(ord('g'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('h'), cc2)

            cc = bf.next_byte()
            self.assertEqual(ord('h'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('i'), cc2)
        
    def test06(self):
        """Test next_byte(3) and peek_byte(3) with a small buffer size"""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)
        
            cc = bf.next_byte()
            self.assertEqual(ord('0'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('1'), cc2)
            cc = bf.next_byte()
            self.assertEqual(ord('1'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('2'), cc2)

            for i in range(12): cc = bf.next_byte()

            # Next byte has index 14
            cc = bf.next_byte()
            self.assertEqual(ord('e'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('f'), cc2)

            cc = bf.next_byte()
            self.assertEqual(ord('f'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('g'), cc2)

            cc = bf.next_byte()
            self.assertEqual(ord('g'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('h'), cc2)

            cc = bf.next_byte()
            self.assertEqual(ord('h'), cc)
            cc2 = bf.peek_byte()
            self.assertEqual(ord('i'), cc2)
            
    def test07(self):
        """Test next_byte(3) and peek_byte(3) with a small buffer size"""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            # Peek before getting any byte
            cc = bf.peek_byte(1)
            self.assertEqual(ord('0'), cc)        
            cc = bf.peek_byte(1)
            self.assertEqual(ord('0'), cc)        
            s = bf.peek_byte(2)
            self.assertEqual(b'01', s)
            s = bf.peek_byte(3)
            self.assertEqual(b'012', s)
            cc = bf.peek_byte(1)
            self.assertEqual(ord('0'), cc)        

            # Get the first byte then peek
            cc = bf.next_byte(1)
            self.assertEqual(ord('0'), cc)
        
            cc = bf.peek_byte(1)
            self.assertEqual(ord('1'), cc)
            s = bf.peek_byte(2)
            self.assertEqual(b'12', s)
            s = bf.peek_byte(3)
            self.assertEqual(b'123', s)

            # Get 3 bytes, so now we're well into the middle of the buffer
            s = bf.next_byte(3)
            self.assertEqual(b'123', s)

            cc = bf.peek_byte(1)
            self.assertEqual(ord('4'), cc)
            s = bf.peek_byte(2)
            self.assertEqual(b'45', s)
            s = bf.peek_byte(3)
            self.assertEqual(b'456', s)
            
    def test08(self):
        """Multiple peeks() across the block boundary (by increasing next's)"""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)
            
            s = bf.next_byte(12)
            self.assertEqual(b'0123456789ab', s)
            s = bf.peek_byte(3)
            self.assertEqual(b'cde', s)  # fully inside the first block
            
            cc = bf.next_byte()
            self.assertEqual(ord('c'), cc)
            s = bf.peek_byte(3)
            self.assertEqual(b'def', s)  # on the rightmost boundary of 1st block
            
            cc = bf.next_byte()
            self.assertEqual(ord('d'), cc)
            s = bf.peek_byte(3)
            self.assertEqual(b'efg', s)  # across the boundary
            
            cc = bf.next_byte()
            self.assertEqual(ord('e'), cc)
            s = bf.peek_byte(3)
            self.assertEqual(b'fgh', s)  # across the boundary
            
            cc = bf.next_byte()
            self.assertEqual(ord('f'), cc)
            s = bf.peek_byte(3)
            self.assertEqual(b'ghi', s)  # on the leftmost boundary of 2nd block
            
            cc = bf.next_byte()
            self.assertEqual(ord('g'), cc)
            s = bf.peek_byte(3)
            self.assertEqual(b'hij', s)  # fully inside the second block
            
            cc = bf.next_byte()
            self.assertEqual(ord('h'), cc)
            s = bf.peek_byte(3)
            self.assertEqual(b'ijk', s)  # fully inside the second block
             
    def test09(self):
        """Multiple peeks() across the block boundary (by increasing peek's)"""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)
            
            s = bf.next_byte(12)
            self.assertEqual(b'0123456789ab', s)

            s = bf.peek_byte(3)
            self.assertEqual(b'cde', s)  # fully inside the first block
            
            s = bf.peek_byte(4)
            self.assertEqual(b'cdef', s)  # on the rightmost boundary of 1st block
            
            s = bf.peek_byte(5)
            self.assertEqual(b'cdefg', s)  # across the boundary
            
            s = bf.peek_byte(6)
            self.assertEqual(b'cdefgh', s)  # across the boundary
            
            s = bf.peek_byte(7)
            self.assertEqual(b'cdefghi', s)  # across the boundary
           
    def test10(self):
        """Block size bigger than the file"""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=64)
            
            s = bf.peek_byte(3)
            self.assertEqual(b'012', s)

            s = bf.next_byte(12)
            self.assertEqual(b'0123456789ab', s)
            s = bf.peek_byte(3)
            self.assertEqual(b'cde', s)  # fully inside the first block
           
    def test11(self):
        """Reading small streams."""
        filepath = os.path.join(ByteStreamTest.path, 'blocks.dat')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            s = bf.next_byte(3)
            self.assertEqual(b'abc', s)

            s = bf.next_stream(4)
            self.assertEqual(b'defg', s)
           
    def test12(self):
        """Reading large streams (greater than multiple block sizes)"""
        filepath = os.path.join(ByteStreamTest.path, 'blocks.dat')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            s = bf.next_byte(3)
            self.assertEqual(b'abc', s)
            s = bf.next_byte(9)
            self.assertEqual(b'j01', s[6:])

            s = bf.next_stream(40)
            self.assertEqual(b'23456789ab', s[:10])
            self.assertEqual(b'cdefghij01', s[30:])

            s = bf.next_byte(3)
            self.assertEqual(b'234', s)                             
           
    def test13(self):
        """Reading large streams, testing boundary conditions 1"""
        filepath = os.path.join(ByteStreamTest.path, 'blocks.dat')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            s = bf.next_stream(80)
            self.assertEqual(b'789', s[77:])
            self.assertEqual(b'0123456789', s[30:40])
           
    def test14(self):
        """Reading large streams, testing boundary conditions 2"""
        filepath = os.path.join(ByteStreamTest.path, 'blocks.dat')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            s = bf.next_byte(16)
            s = bf.next_stream(5)
            self.assertEqual(b'6789a', s)

            s = bf.next_byte(4)
            self.assertEqual(b'bcde', s)
            s = bf.next_stream(3)
            self.assertEqual(b'fgh', s)
            
            s = bf.next_byte(4)
            self.assertEqual(b'ij01', s)
            s = bf.next_stream(3)
            self.assertEqual(b'234', s)
           
    def test15(self):
        """Reading large streams, testing boundary conditions 3"""
        filepath = os.path.join(ByteStreamTest.path, 'blocks.dat')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            s = bf.peek_byte(2)
            self.assertEqual(b'ab', s)
            s = bf.next_stream(2)
            self.assertEqual(b'ab', s)
            

if __name__ == '__main__':
    unittest.main(verbosity=2)

