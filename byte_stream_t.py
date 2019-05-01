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
        """Read some characters, seek back, read again.."""
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
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
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
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
        filepath = os.path.join(ByteStreamTest.path, 'sample.txt')
        with open(filepath, 'rb') as f:
            bf = byte_stream.ByteStream(filepath, f, blk_sz=16)

            # FIle holds 28 bytes of text + CRLF = 30
            s = bf.next_byte(31)
            self.assertEqual(-1, s)
  
if __name__ == '__main__':
    unittest.main(verbosity=2)

