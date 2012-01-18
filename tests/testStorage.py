import unittest
from sfa.trust.gid import *
from sfa.util.config import *
from sfa.storage.persistentobjs import RegRecord

class TestStorage(unittest.TestCase):
    def setUp(self):
        pass

    def testCreate(self):
        r = RegRecord(type='authority',hrn='foo.bar')

if __name__ == "__main__":
    unittest.main()
