#!/usr/bin/env python

import sys
import base64
import struct
import binascii
from M2Crypto import RSA, DSA, m2


###### Workaround for bug in m2crypto-0.18 (on Fedora 8)
class RSA_pub_fix(RSA.RSA_pub):
    def save_key_bio(self, bio, *args, **kw):
        return self.save_pub_key_bio(bio)

def rsa_new_pub_key((e, n)):
    rsa = m2.rsa_new()
    m2.rsa_set_e(rsa, e)
    m2.rsa_set_n(rsa, n)
    return RSA_pub_fix(rsa, 1)
######
#rsa_new_pub_key = RSA.new_pub_key


def decode_key(fname):
    """Convert base64 encoded openssh key to binary"""
    contents = open(fname).read()
    fields = contents.split()

    in_key = False
    for f in fields:
        f = f.strip()
        if f.startswith("ssh-"):
            in_key = True
            continue
        elif in_key:
            return base64.b64decode(f)
        
    return None


# openssh binary key format
#
# a section:
# length = 4 bytes (32-bit big-endian integer)
# data = length bytes of string 
# 
# sections of the key ( for RSA )
# [key-type (in ASCII)] [public exponent (bignum)] [primes (bignum)]
#
# sections of the key ( for DSA )
# [key-type (in ASCII)] [p (bignum)] [q (bignum)] [g (bignum)] [y (bignum)]
#
# - baris
def read_key(key):
    
    def read_length(key):
        length = key[0:4]
        length = struct.unpack(">l", length)[0]
        return length, key
        
    def read_values(key, count):
        v = []
        for i in range(count):
            length, key = read_length(key)
            size = 4 + length
            v.append(key[:size])
            key = key[size:]
        return v

    length, key = read_length(key)
    key = key[4:]
    key_type = key[:length]
    key = key[length:]

    if key_type == "ssh-rsa":
        # prepare parameters for RSA.new_pub_key
        v = read_values(key, 2)
        e, n = v[0], v[1]
        return key_type, e, n

    elif key_type == "ssh-dss":
        # prepare parameters for DSA.set_params
        v = read_values(key, 4)
        p, q, g, y = v[0], v[1], v[2], v[3]
        return key_type, p, q, g, y


def convert(fin, fout):
    key = decode_key(fin)
    ret = read_key(key)
    key_type = ret[0]

    if key_type == "ssh-rsa":
        e, n = ret[1:]
        rsa = rsa_new_pub_key((e, n))
        rsa.save_pem(fout)

    elif key_type == "ssh-dss":
        p, q, g, y = ret[1:]
        dsa = DSA.set_params(p, q, g)
        dsa.gen_key()
        dsa.save_pub_key(fout)
        # FIXME: This is wrong.
        # M2Crypto doesn't allow us to set the public key parameter
        raise(Exception, "DSA keys are not supported yet: M2Crypto doesn't allow us to set the public key parameter")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print "Usage: %s <input-file> <output-file>"
        sys.exit(1)

    fin = sys.argv[1]
    fout = sys.argv[2]
    convert(fin, fout)
