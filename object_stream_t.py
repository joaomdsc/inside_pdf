#!/usr/bin/env python
# object_stream_t.py

import os
import unittest
from object_stream import EObject, ObjectStream

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

class ObjectStreamTest(unittest.TestCase):
    """Test the parsing of pdf objects in pdf files."""

    path = r'D:\joao\src\py\pdf\t'

    def test01(self):
        """Test simple next_object() calls."""
        filepath = os.path.join(ObjectStreamTest.path, 'obj_stream1.dat')
        with open(filepath, 'rb') as f:
            ob = ObjectStream(filepath, f)

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
        filepath = os.path.join(ObjectStreamTest.path, 'obj_stream1.dat')
        with open(filepath, 'rb') as f:
            ob = ObjectStream(filepath, f)

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
        filepath = os.path.join(ObjectStreamTest.path, 'obj_stream2.dat')
        with open(filepath, 'rb') as f:
            ob = ObjectStream(filepath, f)

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

    def test04(self):
        """Test indirect object references."""
        filepath = os.path.join(ObjectStreamTest.path, 'obj_stream3.dat')
        with open(filepath, 'rb') as f:
            ob = ObjectStream(filepath, f)

            # First object is an indirect object ref (ior)
            obj = ob.next_object()
            self.assertEqual(EObject.IND_OBJ_REF, obj.type)
            self.assertEqual(125, obj.data['objn'])
            self.assertEqual(0, obj.data['gen'])

            # Second object is an array
            obj = ob.next_object()
            self.assertEqual(EObject.ARRAY, obj.type)
            arr = obj.data
            self.assertEqual(3, len(arr))

            o = arr[0]
            self.assertEqual(EObject.IND_OBJ_REF, o.type)
            self.assertEqual(13, o.data['objn'])
            self.assertEqual(2, o.data['gen'])

            o = arr[1]
            self.assertEqual(EObject.INTEGER, o.type)
            self.assertEqual(51, o.data)

            o = arr[2]
            self.assertEqual(EObject.IND_OBJ_REF, o.type)
            self.assertEqual(42, o.data['objn'])
            self.assertEqual(0, o.data['gen'])

    def test05(self):
        """Test dictionary objects in dict1.dat."""
        filepath = os.path.join(ObjectStreamTest.path, 'dict1.dat')
        with open(filepath, 'rb') as f:
            ob = ObjectStream(filepath, f)

            # Retrieve a dictionary
            obj = ob.next_object()
            self.assertEqual(EObject.DICTIONARY, obj.type)
            # Contains 2 keys 
            d = obj.data
            self.assertEqual(2, len(d))
            self.assertEqual(15, d['aaa'].data)
            self.assertEqual(9, d['bb'].data)

            # Retrieve a dictionary
            obj = ob.next_object()
            self.assertEqual(EObject.DICTIONARY, obj.type)
            # Contains 3 keys 
            d = obj.data
            self.assertEqual(3, len(d))
            self.assertEqual(b'peter', d['cc'].data)
            self.assertEqual(b'paul', d['dd'].data)
            arr = d['ee'].data
            self.assertEqual(2, len(arr))
            self.assertEqual(1, arr[0].data)
            self.assertEqual(2, arr[1].data)

            # Retrieve a dictionary
            obj = ob.next_object()
            self.assertEqual(EObject.DICTIONARY, obj.type)
            # Contains 4 keys 
            d = obj.data
            self.assertEqual(4, len(d))
            d2 = d['dd'].data
            self.assertEqual(3, len(d2))
            o2 = d2['a1']
            self.assertEqual(EObject.ARRAY, o2.type)
            arr = o2.data
            self.assertEqual(3, len(arr))
            self.assertEqual(5, arr[0].data)
            self.assertEqual(7, arr[1].data)
            self.assertEqual(9, arr[2].data)

            # Retrieve a dictionary
            obj = ob.next_object()
            self.assertEqual(EObject.DICTIONARY, obj.type)
            # Contains 1 key 'a'
            d = obj.data
            self.assertEqual(1, len(d))
            # a's value is a dictionary 'x'
            x = d['a']
            self.assertEqual(EObject.DICTIONARY, x.type)
            y = x.data
            self.assertEqual(1, len(y))
            # b's value is a name
            x3 = y['b']
            self.assertEqual(EObject.NAME, x3.type)
            self.assertEqual(b'x', x3.data)

            # Retrieve a dictionary
            obj = ob.next_object()
            self.assertEqual(EObject.DICTIONARY, obj.type)
            # Contains 1 key 'a'
            d = obj.data
            self.assertEqual(1, len(d))
            # a's value is a dictionary 'x'
            x = d['a']
            self.assertEqual(EObject.DICTIONARY, x.type)
            y = x.data
            self.assertEqual(1, len(y))
            # b's value is a dictionary x2
            x2 = y['b']
            self.assertEqual(EObject.DICTIONARY, x2.type)
            y2 = x2.data
            self.assertEqual(1, len(y2))
            # v's value is a name
            x3 = y2['v']
            self.assertEqual(EObject.NAME, x3.type)
            self.assertEqual(b'z', x3.data)

    def test06(self):
        """Test dictionary objects in dict2.dat"""
        filepath = os.path.join(ObjectStreamTest.path, 'dict2.dat')
        with open(filepath, 'rb') as f:
            ob = ObjectStream(filepath, f)

            # Retrieve a dictionary
            obj = ob.next_object()
            self.assertEqual(EObject.DICTIONARY, obj.type)
            # Contains 8 keys 
            d = obj.data
            self.assertEqual(8, len(d))

            val = d['Type']
            self.assertEqual(EObject.NAME, val.type)
            self.assertEqual(b'Page', val.data)

            val = d['MediaBox']
            self.assertEqual(EObject.ARRAY, val.type)
            arr = val.data
            self.assertEqual(4, len(arr))
            self.assertEqual(595, arr[2].data)

            val = d['Resources']
            self.assertEqual(EObject.DICTIONARY, val.type)
            d2 = val.data
            self.assertEqual(3, len(d2))

            val = d2['Font']
            self.assertEqual(EObject.DICTIONARY, val.type)
            d3 = val.data
            self.assertEqual(3, len(d3))

            val = d3['Z_F17']
            self.assertEqual(EObject.IND_OBJ_REF, val.type)
            self.assertEqual(6114, val.data['objn'])
            self.assertEqual(0, val.data['gen'])

if __name__ == '__main__':
    unittest.main(verbosity=2)

