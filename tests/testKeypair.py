#!/usr/bin/python
import sys
sys.path.append('..')

import unittest
import base64
from sfa.trust.certificate import Keypair

class TestKeypair(unittest.TestCase):
   def setUp(self):
      pass

   def testCreate(self):
      k = Keypair()
      k.create()

   def testSaveLoadFile(self):
      k = Keypair()
      k.create()

      k.save_to_file("test.key")

      k2 = Keypair()
      k2.load_from_file("test.key")

      self.assertEqual(k.as_pem(), k2.as_pem())

   def test_get_m2_pkey(self):
      k = Keypair()
      k.create()

      m2 = k.get_m2_pkey()
      self.assert_(m2 != None)

   def test_get_openssl_pkey(self):
      k = Keypair()
      k.create()

      pk = k.get_openssl_pkey()
      self.assert_(pk != None)

   def test_sign_verify(self):
      k = Keypair()
      k.create()

      data = "this is a test"
      sig = k.sign_string(data)

      print k.verify_string(data, sig)

if __name__ == "__main__":
    unittest.main()
