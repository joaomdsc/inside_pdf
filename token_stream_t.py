#!/usr/bin/env python
# token_stream_t.py

import os
import unittest
from token_stream import EToken, TokenStream

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

class TokenStreamTest(unittest.TestCase):
    """Test the parsing of binary files."""

    path = 't'

    # FIXME: define a systematic collection of tests on each type of
    # token. Test with and without whitespace/eol

    def test01(self):
        """Test simple next_token() and peek_token() calls."""
        filepath = os.path.join(TokenStreamTest.path, 'token_stream.dat')
        with open(filepath, 'rb') as f:
            tk = TokenStream(filepath, f)

            # Retrieve a few tokens
            tok = tk.next_token()
            self.assertEqual(EToken.DICT_BEGIN, tok.type)
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'Contents', tok.data)
            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(6624, tok.data)

            # Now peek once
            tok2 = tk.peek_token()
            self.assertEqual(EToken.INTEGER, tok2.type)
            self.assertEqual(0, tok2.data)

            # Retrieve a peeked token
            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(0, tok.data)

            # Peek 3 tokens ahead
            tok2 = tk.peek_token()
            self.assertEqual(EToken.OBJ_REF, tok2.type)
            tok2 = tk.peek_token()
            self.assertEqual(EToken.NAME, tok2.type)
            self.assertEqual(b'CropBox', tok2.data)
            tok2 = tk.peek_token()
            self.assertEqual(EToken.ARRAY_BEGIN, tok2.type)

            # Retrieve 2 tokens
            tok = tk.next_token()
            self.assertEqual(EToken.OBJ_REF, tok.type)
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'CropBox', tok.data)

            # I still have the ARRAY_BEGIN in 'peeked'

            # I'm not sure this is the right spec... 

            # Peeking 5 more
            tok2 = tk.peek_token()
            self.assertEqual(EToken.INTEGER, tok2.type)
            self.assertEqual(0, tok2.data)
            tok2 = tk.peek_token()
            self.assertEqual(EToken.INTEGER, tok2.type)
            self.assertEqual(0, tok2.data)
            tok2 = tk.peek_token()
            self.assertEqual(EToken.REAL, tok2.type)
            self.assertEqual(595.276, tok2.data)
            tok2 = tk.peek_token()
            self.assertEqual(EToken.REAL, tok2.type)
            self.assertEqual(841.89, tok2.data)
            tok2 = tk.peek_token()
            self.assertEqual(EToken.ARRAY_END, tok2.type)

            # Retrieve 1 plus 5 plus 1
            tok = tk.next_token()
            self.assertEqual(EToken.ARRAY_BEGIN, tok.type)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(0, tok.data)
            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(0, tok.data)
            tok = tk.next_token()
            self.assertEqual(EToken.REAL, tok.type)
            self.assertEqual(595.276, tok.data)
            tok = tk.next_token()
            self.assertEqual(EToken.REAL, tok.type)
            self.assertEqual(841.89, tok.data)
            tok = tk.next_token()
            self.assertEqual(EToken.ARRAY_END, tok.type)

            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'MediaBox', tok.data)

    def test02(self):
        """Test simple next_token() calls."""
        filepath = r't\token.dat'
        with open(filepath, 'rb') as f:
            tk = TokenStream(filepath, f)

            # [[[
            tok = tk.next_token()
            self.assertEqual(EToken.ARRAY_BEGIN, tok.type)
            tok = tk.next_token()
            self.assertEqual(EToken.ARRAY_BEGIN, tok.type)
            tok = tk.next_token()
            self.assertEqual(EToken.ARRAY_BEGIN, tok.type)

            # <<>> >>
            tok = tk.next_token()
            self.assertEqual(EToken.DICT_BEGIN, tok.type)
            tok = tk.next_token()
            self.assertEqual(EToken.DICT_END, tok.type)
            tok = tk.next_token()
            self.assertEqual(EToken.DICT_END, tok.type)

            # ]
            tok = tk.next_token()
            self.assertEqual(EToken.ARRAY_END, tok.type)
            
            # /// 
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'', tok.data)
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'', tok.data)
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'', tok.data)

            for i in range(6):
                tok = tk.next_token()

            # >>\r\n<<
            tok = tk.next_token()
            self.assertEqual(EToken.DICT_END, tok.type)
            tok = tk.next_token()
            self.assertEqual(EToken.CRLF, tok.type)
            tok = tk.next_token()
            self.assertEqual(EToken.DICT_BEGIN, tok.type)

            # /a
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'a', tok.data)

            # /b
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'b', tok.data)
            # /c
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'c', tok.data)
            # /d
            tok = tk.next_token()
            self.assertEqual(EToken.NAME, tok.type)
            self.assertEqual(b'd', tok.data)
            tok = tk.next_token()
            self.assertEqual(EToken.DICT_END, tok.type)

    def test04(self):
        """Test token seek and tell."""
        filepath = os.path.join(TokenStreamTest.path, 'obj_stream3.dat')
        with open(filepath, 'rb') as f:
            tk = TokenStream(filepath, f)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(98, tok.data)

            # Memorize position after doing a first next_token(), this works
            xpos = tk.tell()

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(73, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(5, tok.data)
            
            tk.seek(xpos)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(73, tok.data)

    def test05(self):
        """Test token seek and tell."""
        filepath = os.path.join(TokenStreamTest.path, 'obj_stream3.dat')
        with open(filepath, 'rb') as f:
            tk = TokenStream(filepath, f)

            # Memorize position at the beginning, this bugs
            xpos = tk.tell()

            # tk.seek(0)
            # print(f'test05: seek(0): cc="{chr(tk.cc)}", bf.s_pos={tk.bf.s_pos}')

            # tk.seek(1)
            # print(f'test05: seek(1), cc="{chr(tk.cc)}", bf.s_pos={tk.bf.s_pos}')

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(98, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(73, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(5, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(19, tok.data)

            pos2 = tk.tell()

            # Go back
            tk.seek(xpos)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(98, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(73, tok.data)

            # Move forward
            tk.seek(pos2)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(18, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(33, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(45, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(66, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(13, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.INTEGER, tok.type)
            self.assertEqual(2, tok.data)

            tok = tk.next_token()
            self.assertEqual(EToken.OBJ_REF, tok.type)
            

if __name__ == '__main__':
    unittest.main(verbosity=2)

