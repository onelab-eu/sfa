import unittest
import xmlrpclib
from sfa.trust.gid import *
from sfa.util.config import *
from sfa.storage.record import *

class TestRecord(unittest.TestCase):
    def setUp(self):
        pass

    def testCreate(self):
        r = SfaRecord()

if __name__ == "__main__":
    unittest.main()
