import unittest
from sfa.trust.certificate import Keypair
from sfa.trust.gid import *

class TestGid(unittest.TestCase):
   def setUp(self):
      pass

   def testSetGetHrn(self):
      gid = GID(subject="test")
      hrn = "test.hrn"

      gid.set_hrn(hrn)
      self.assertEqual(gid.get_hrn(), hrn)

   def testSetGetUuid(self):
      gid = GID(subject="test")
      u = uuid.uuid4().int

      gid.set_uuid(u)
      self.assertEqual(gid.get_uuid(), u)

   def testEncodeDecode(self):
      gid = GID(subject="test")
      u = uuid.uuid4().int
      hrn = "test.hrn"

      gid.set_uuid(u)
      gid.set_hrn(hrn)

      gid.encode()
      gid.decode()

      self.assertEqual(gid.get_hrn(), hrn)
      self.assertEqual(gid.get_uuid(), u)

   def testSaveAndLoadString(self):
      gid = GID(subject="test")

      u = uuid.uuid4().int
      hrn = "test.hrn"

      gid.set_uuid(u)
      gid.set_hrn(hrn)

      # create an issuer and sign the certificate
      issuerKey =  Keypair(create = True)
      issuerSubject = "testissuer"
      gid.set_issuer(issuerKey, issuerSubject)
      gid.sign()

      certstr = gid.save_to_string()

      #print certstr

      gid2 = GID(string = certstr)

      self.assertEqual(gid.get_hrn(), hrn)
      self.assertEqual(gid.get_uuid(), u)

if __name__ == "__main__":
    unittest.main()
