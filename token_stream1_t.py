#!/usr/bin/env python
# token_stream1_t.py

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
    """Test the parsing of literal strings."""

    def test_literal01(self):
        """Test the set of example strings from the spec."""
        filepath = 't/literal01.dat'
        with open(filepath, 'rb') as f:
            tk = TokenStream(filepath, f)

            # This is a string
            tok = tk.next_token()
            self.assertEqual(EToken.LITERAL_STRING, tok.type)
            b = tok.data
            self.assertEqual(16, len(b))
            self.assertEqual(b'This', b[0:4])

            # Skip over end of lines
            while True:
                tok = tk.next_token()
                if tok.type not in [EToken.CR, EToken.LF, EToken.CRLF]:
                    break

            # Strings may contain newlines\n and such
            self.assertEqual(EToken.LITERAL_STRING, tok.type)
            b = tok.data
            self.assertTrue(b.startswith(b'Strings may'))
            self.assertTrue(b.endswith(b'such.'))

            # Skip over end of lines
            while True:
                tok = tk.next_token()
                if tok.type not in [EToken.CR, EToken.LF, EToken.CRLF]:
                    break
                
            # Strings may contain balanced parentheses...
            self.assertEqual(EToken.LITERAL_STRING, tok.type)
            b = tok.data
            self.assertEqual(b'(x)', b[41:44])
            self.assertTrue(b.endswith(b'% and so on).'))

            # Skip over end of lines
            while True:
                tok = tk.next_token()
                if tok.type not in [EToken.CR, EToken.LF, EToken.CRLF]:
                    break

            # The following is an empty string.
            self.assertEqual(EToken.LITERAL_STRING, tok.type)
            b = tok.data
            self.assertEqual(b'The following is an empty string.', b)
            while True:
                tok = tk.next_token()
                if tok.type not in [EToken.CR, EToken.LF, EToken.CRLF]:
                    break

            # Empty string
            self.assertEqual(EToken.LITERAL_STRING, tok.type)
            b = tok.data
            self.assertEqual(0, len(b))
            self.assertEqual(b'', b)

            # Skip over end of lines
            while True:
                tok = tk.next_token()
                if tok.type not in [EToken.CR, EToken.LF, EToken.CRLF]:
                    break

            # It has zero (0) length.
            self.assertEqual(EToken.LITERAL_STRING, tok.type)
            b = tok.data
            self.assertEqual(23, len(b))
            self.assertEqual(b'It has zero (0) length.', b)

    def test_literal02(self):
        """Test escape sequences in literal strings."""
        filepath = 't/literal02.dat'
        with open(filepath, 'rb') as f:
            tk = TokenStream(filepath, f)

            # This is a string
            tok = tk.next_token()
            self.assertEqual(EToken.LITERAL_STRING, tok.type)
            b = tok.data
            self.assertEqual(2, len(b))
            self.assertEqual(40, b[0])
            self.assertEqual(41, b[1])

    def test_literal03(self):
        """Test escape sequences in literal strings."""
        filepath = 't/literal03.dat'
        with open(filepath, 'rb') as f:
            tk = TokenStream(filepath, f)

            # This is a string
            tok = tk.next_token()
            self.assertEqual(EToken.LITERAL_STRING, tok.type)
            b = tok.data
            for i in b:
                print(f'i="{i}"')
            self.assertEqual(9, len(b))
            self.assertEqual(13, b[0])  # \r CR
            self.assertEqual(10, b[1])  # \n LF
            print(f'b[2]="{b[2]}"')
            self.assertEqual(8, b[2])   # \b BS
            self.assertEqual(9, b[3])   # \t TAB
            self.assertEqual(12, b[4])
            self.assertEqual(40, b[5])
            self.assertEqual(41, b[6])
            self.assertEqual(0x5c, b[7])
            self.assertEqual(83, b[8])

            # # Skip over end of lines
            # while True:
            #     tok = tk.next_token()
            #     if tok.type not in [EToken.CR, EToken.LF, EToken.CRLF]:
            #         break

if __name__ == '__main__':
    unittest.main(verbosity=2)

