#!/usr/bin/python
##
# Delete all the database records for SFA. This tool is used to clean out SFA
# records during testing.
#
# Authority info (maintained by the hierarchy module in a subdirectory tree)
# is not purged by this tool and may be deleted by a command like 'rm'.
##

import sys
import os
from optparse import OptionParser

from sfa.util.sfalogging import logger

from sfa.storage.table import SfaTable

def main():
   usage="%prog: trash the registry DB (the 'sfa' table in the 'planetlab5' database)"
   parser = OptionParser(usage=usage)
   parser.add_option('-f','--file-system',dest='clean_fs',action='store_true',default=False,
                     help='Clean up the /var/lib/sfa/authorities area as well')
   parser.add_option('-c','--certs',dest='clean_certs',action='store_true',default=False,
                     help='Remove all cached certs/gids found in /var/lib/sfa/authorities area as well')
   (options,args)=parser.parse_args()
   if args:
      parser.print_help()
      sys.exit(1)
   logger.info("Purging SFA records from database")
   table = SfaTable()
   table.sfa_records_purge()

   if options.clean_certs:
      # remove the server certificate and all gids found in /var/lib/sfa/authorities
      logger.info("Purging cached certificates")
      for (dir, _, files) in os.walk('/var/lib/sfa/authorities'):
         for file in files:
            if file.endswith('.gid') or file == 'server.cert':
               path=dir+os.sep+file
               os.unlink(path)
               if not os.path.exists(path):
                  logger.info("Unlinked file %s"%path)
               else:
                  logger.error("Could not unlink file %s"%path)

   if options.clean_fs:
      # just remove all files that do not match 'server.key' or 'server.cert'
      logger.info("Purging registry filesystem cache")
      preserved_files = [ 'server.key', 'server.cert']
      for (dir,_,files) in os.walk('/var/lib/sfa/authorities'):
         for file in files:
            if file in preserved_files: continue
            path=dir+os.sep+file
            os.unlink(path)
            if not os.path.exists(path):
               logger.info("Unlinked file %s"%path)
            else:
               logger.error("Could not unlink file %s"%path)
if __name__ == "__main__":
   main()
