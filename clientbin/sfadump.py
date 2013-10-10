#! /usr/bin/env python
from __future__ import with_statement

import sys
import os, os.path
import tempfile
from types import StringTypes, ListType
from argparse import ArgumentParser

from sfa.util.sfalogging import logger
from sfa.util.faults import CredentialNotVerifiable, CertMissingParent #, ChildRightsNotSubsetOfParent

from sfa.trust.certificate import Certificate
from sfa.trust.credential import Credential
from sfa.trust.gid import GID

from sfa.storage.record import Record

def determine_sfa_filekind(fn):

    if fn.endswith('.gid'): return 'gid'
    elif fn.endswith('.cert'): return 'certificate'
    elif fn.endswith('cred'): return 'credential'

    try:
        cred=Credential(filename=fn)
        return 'credential'
    except: pass

    try: 
        gid=GID(filename=fn)
        if gid.uuid: return 'gid'
    except: pass

    try:
        cert = Certificate(filename = fn)
        return 'certificate'
    except: pass

    # to be completed
#    if "gidCaller" in dict:
#        return "credential"
#
#    if "uuid" in dict:
#        return "gid"

    return "unknown"

def save_gid(gid):
   hrn = gid.get_hrn()
   lastpart = hrn.split(".")[-1]
   filename = lastpart + ".gid"

   if os.path.exists(filename):
       print filename, ": already exists... skipping"
       return

   print filename, ": extracting gid of", hrn

   gid.save_to_file(filename, save_parents = True)

def extract_gids(cred, extract_parents):
   gidCaller = cred.get_gid_caller()
   if gidCaller:
       save_gid(gidCaller)

   gidObject = cred.get_gid_object()
   if gidObject and ((gidCaller == None) or (gidCaller.get_hrn() != gidObject.get_hrn())):
       save_gid(gidObject)

   # no such method Credential.get_parent
#   if extract_parents:
#       parent = cred.get_parent()
#       if parent:
#           extract_gids(parent, extract_parents)

def verify_input_object (obj, kind, options):
    if options.trusted_roots:
        print "CHECKING...",
        message= "against [" + (" + ".join(options.trusted_roots)) + "]"
        try:
            if kind=='credential':
                print "verify",message,
                obj.verify(options.trusted_roots)
            elif kind in ['certificate','gid']:
                print "verify_chain",message,
                obj.verify_chain(options.trusted_roots)
            print "--> OK"
        except Exception as inst:
            print "--> KO",type(inst).__name__

def handle_input (filename, options):
    kind = determine_sfa_filekind(filename)

    # dump methods current do 'print' so let's go this road for now
    if kind=="certificate":
        cert=Certificate (filename=filename)
        print '--------------------',filename,'IS A',kind
        cert.dump(show_extensions=options.show_extensions)
        verify_input_object (cert, kind, options)
    elif kind=="credential":
        cred = Credential(filename = filename)
        print '--------------------',filename,'IS A',kind
        cred.dump(dump_parents = options.dump_parents, show_xml=options.show_xml)
        if options.extract_gids:
            print '--------------------',filename,'embedded GIDs'
            extract_gids(cred, extract_parents = options.dump_parents)
        verify_input_object (cred, kind, options)
    elif kind=="gid":
        gid = GID(filename = filename)
        print '--------------------',filename,'IS A',kind
        gid.dump(dump_parents = options.dump_parents)
        verify_input_object (gid, kind, options)
    else:
        print "%s: unknown filekind '%s'"% (filename,kind)

def main():
    usage = """%prog file1 [ .. filen]
display info on input files"""
    parser = ArgumentParser(usage=usage)

    parser.add_argument("-g", "--extract-gids", action="store_true", dest="extract_gids", 
                        default=False, help="Extract GIDs from credentials")
    parser.add_argument("-p", "--dump-parents", action="store_true", dest="dump_parents", 
                        default=False, help="Show parents")
    parser.add_argument("-e", "--extensions", action="store_true", 
                        dest="show_extensions", default="False", help="Show certificate extensions")
    parser.add_argument("-v", "--verbose", action='count', 
                        dest='verbose', default=0, help="More and more verbose")
    parser.add_argument("-x", "--xml", action='store_true', 
                        dest='show_xml', default=False, help="dumps xml tree (cred. only)")
    parser.add_argument("-c", "--check", action='append', dest='trusted_roots',
                        help="cumulative list of trusted GIDs - when provided, the input is verify'ed against these")
    parser.add_argument("filenames",metavar='F',nargs='+',help="filenames to dump")
    options = parser.parse_args()

    logger.setLevelFromOptVerbose(options.verbose)
    for filename in options.filenames: 
        handle_input(filename,options)

if __name__=="__main__":
   main()
