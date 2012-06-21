#! /usr/bin/env python
from __future__ import with_statement

import sys
import os, os.path
import tempfile
from types import StringTypes, ListType
from optparse import OptionParser

from sfa.util.sfalogging import logger

from sfa.trust.certificate import Certificate
from sfa.trust.credential import Credential
from sfa.trust.gid import GID

from sfa.storage.record import SfaRecord

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

def handle_input (filename, options):
    kind = determine_sfa_filekind(filename)
    handle_input_kind (filename,options,kind)

def handle_input_kind (filename, options, kind):
    

# dump methods current do 'print' so let's go this road for now
    if kind=="certificate":
        cert=Certificate (filename=filename)
        print '--------------------',filename,'IS A',kind
        cert.dump(show_extensions=options.show_extensions)
    elif kind=="credential":
        cred = Credential(filename = filename)
        print '--------------------',filename,'IS A',kind
        cred.dump(dump_parents = options.dump_parents)
        if options.extract_gids:
            print '--------------------',filename,'embedded GIDS'
            extract_gids(cred, extract_parents = options.dump_parents)
    elif kind=="gid":
        gid = GID(filename = filename)
        print '--------------------',filename,'IS A',kind
        gid.dump(dump_parents = options.dump_parents)
    else:
        print "%s: unknown filekind '%s'"% (filename,kind)

def main():
    usage = """%prog file1 [ .. filen]
display info on input files"""
    parser = OptionParser(usage=usage)

    parser.add_option("-g", "--extract-gids", action="store_true", dest="extract_gids", default=False, help="Extract GIDs from credentials")
    parser.add_option("-p", "--dump-parents", action="store_true", dest="dump_parents", default=False, help="Show parents")
    parser.add_option("-e", "--extensions", action="store_true", dest="show_extensions", default="False", help="Show certificate extensions")
    parser.add_option("-v", "--verbose", action='count', dest='verbose', default=0)
    (options, args) = parser.parse_args()

    logger.setLevelFromOptVerbose(options.verbose)
    if len(args) <= 0:
        parser.print_help()
        sys.exit(1)
    for f in args: 
        handle_input(f,options)

if __name__=="__main__":
   main()
