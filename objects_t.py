#!/usr/bin/env python
# objects_t.py

import os
import unittest
from objects import EObject, ObjStream

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

class ObjectsTest(unittest.TestCase):
    """Test the parsing of binary files."""

    path = r'D:\joao\src\py\pdf\t'

    def test01(self):
        """Test simple next_object() calls."""
        filepath = os.path.join(ObjectsTest.path, 'obj_stream1.txt')
        with open(filepath, 'rb') as f:
            ob = ObjStream(filepath, f)

            # Retrieve a few tokens
            obj = ob.next_object()
            self.assertEqual(EObject.NAME, obj.type)
            self.assertEqual(b'CropBox', obj.data)
            obj = ob.next_object()
            self.assertEqual(EObject.INTEGER, obj.type)
            self.assertEqual(4301, obj.data)
            obj = ob.next_object()
            self.assertEqual(EObject.INTEGER, obj.type)
            self.assertEqual(0, obj.data)
            obj = ob.next_object()
            self.assertEqual(EObject.ARRAY, obj.type)
            obj = ob.next_object()
            self.assertEqual(EObject.STRING, obj.type)
            self.assertEqual(b'Hello', obj.data)

    def test02(self):
        """Test nested arrays."""
        filepath = os.path.join(ObjectsTest.path, 'obj_stream1.txt')
        with open(filepath, 'rb') as f:
            ob = ObjStream(filepath, f)

            # Retrieve a few tokens
            obj = ob.next_object()
            self.assertEqual(EObject.NAME, obj.type)
            self.assertEqual(b'CropBox', obj.data)
            obj = ob.next_object()
            self.assertEqual(EObject.INTEGER, obj.type)
            self.assertEqual(4301, obj.data)
            obj = ob.next_object()
            self.assertEqual(EObject.INTEGER, obj.type)
            self.assertEqual(0, obj.data)

            # Array
            obj = ob.next_object()
            self.assertEqual(EObject.ARRAY, obj.type)

            # arr is a python array, but the items are PdfObjects
            arr = obj.data
            self.assertEqual(5, len(arr))

            # Second item is a 4-item array
            o2 = arr[2]
            self.assertEqual(EObject.ARRAY, o2.type)
            self.assertEqual(4, len(o2.data))
            x = o2.data[0]
            self.assertEqual(EObject.STRING, x.type)
            self.assertEqual(b'a', x.data)
            x = o2.data[3]
            self.assertEqual(EObject.INTEGER, x.type)
            self.assertEqual(91, x.data)

            obj = ob.next_object()
            self.assertEqual(EObject.STRING, obj.type)
            self.assertEqual(b'Hello', obj.data)

    def test03(self):
        """Test nested dictionaries."""
        filepath = os.path.join(ObjectsTest.path, 'obj_stream2.txt')
        with open(filepath, 'rb') as f:
            ob = ObjStream(filepath, f)

            # Retrieve a few tokens
            obj = ob.next_object()
            self.assertEqual(EObject.INTEGER, obj.type)
            self.assertEqual(13, obj.data)
            obj = ob.next_object()
            self.assertEqual(EObject.NAME, obj.type)
            self.assertEqual(b'byebye', obj.data)

            # Third item is a dictionary
            obj = ob.next_object()
            self.assertEqual(EObject.DICTIONARY, obj.type)

            # d is a python dictionary, but the items are PdfObjects
            d = obj.data
            self.assertEqual(6, len(d))

            x = d['Second']
            self.assertEqual(EObject.REAL, x.type)
            self.assertEqual(841.89, x.data)

            x = d['Goodbye']
            self.assertEqual(EObject.STRING, x.type)
            self.assertEqual(b'goodnight', x.data)

            # The Sub key holds a dictionary value
            x = d['Sub']
            self.assertEqual(EObject.DICTIONARY, x.type)
            self.assertEqual(4, len(x.data))

            y = x.data['lower']
            self.assertEqual(EObject.DICTIONARY, y.type)
            self.assertEqual(2, len(y.data))

            z = y.data['Black']
            self.assertEqual(EObject.INTEGER, z.type)
            self.assertEqual(1, z.data)

            y = x.data['nice']
            self.assertEqual(EObject.REAL, y.type)
            self.assertEqual(1.0, y.data)

if __name__ == '__main__':
    unittest.main(verbosity=2)

