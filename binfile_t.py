# binfile_t.py

import os
import unittest
import binfile

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

class BinFileTest(unittest.TestCase):
    """Test the parsing of binary files."""

    path = r'D:\joao\src\py\pdf\t'

    # This is stupid. With binary files, CR and LF are not treated specially.
    
    def test01(self):
        """Test next_byte() and peek_byte() with dos-style line endings"""
        # Lines are not empty
        bf = binfile.BinFile(os.path.join(BinFileTest.path, 't01_dos_crlf.pdf'))

        # Read the entire first line, plus a couple of characters in the next
        # one, checking both next_byte() and peek_byte().
        cc = bf.next_byte()
        self.assertEqual(ord('y'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('a'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('a'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('z'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('z'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('b'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('b'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(0x0d, cc2)
        
        cc = bf.next_byte()
        self.assertEqual(0x0d, cc)
        cc2 = bf.peek_byte()
        self.assertEqual(0x0a, cc2)
        
        cc = bf.next_byte()
        self.assertEqual(0x0a, cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('6'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('6'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('7'), cc2)
        
        bf.close()
    
    def test02(self):
        """Test next_byte() and peek_byte() with mac-style line endings"""
        # Lines are not empty
        bf = binfile.BinFile(os.path.join(BinFileTest.path, 't01_mac_cr.pdf'))

        # Read the entire first line, plus a couple of characters in the next
        # one, checking both next_byte() and peek_byte().
        cc = bf.next_byte()
        self.assertEqual(ord('r'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('e'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('e'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('s'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('s'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('f'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('f'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(0x0d, cc2)
        
        cc = bf.next_byte()
        self.assertEqual(0x0d, cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('3'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('3'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('9'), cc2)
        
        bf.close()
    
    def test03(self):
        """Test next_byte() and peek_byte() with unix-style line endings"""
        # Lines are not empty
        bf = binfile.BinFile(os.path.join(BinFileTest.path, 't01_unix_lf.pdf'))

        # Read the entire first line, plus a couple of characters in the next
        # one, checking both next_byte() and peek_byte().
        cc = bf.next_byte()
        self.assertEqual(ord('a'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('b'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('b'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('c'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('c'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('d'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('d'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(0x0a, cc2)
        
        cc = bf.next_byte()
        self.assertEqual(0x0a, cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('p'), cc2)
        
        cc = bf.next_byte()
        self.assertEqual(ord('p'), cc)
        cc2 = bf.peek_byte()
        self.assertEqual(ord('p'), cc2)
        
        bf.close()

    def test04(self):
        """Test next_byte() and peek_byte() with a small buffer size"""
        filepath = os.path.join(BinFileTest.path, 'sample.txt')
        bf = binfile.BinFile(filepath, blk_sz=16)
        
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
        
        bf.close()
        
if __name__ == '__main__':
    unittest.main(verbosity=2)

