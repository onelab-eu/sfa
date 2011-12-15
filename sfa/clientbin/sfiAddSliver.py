#! /usr/bin/env python

import sys

from sfa.util.sfalogging import logger
from sfa.client.sfi_commands import Commands
from sfa.rspecs.rspec import RSpec
from sfa.rspecs.version_manager import VersionManager

logger.enable_console()
command = Commands(usage="%prog [options] node1 node2...",
                   description="Add slivers to the RSpec. " +
                   "This command reads in an RSpec and outputs a modified " +
                   "RSpec. Use this to add nodes to your slice.")
command.add_nodefile_option()
command.prep()

if not command.opts.nodefile:
    print "Missing node list -- exiting"
    command.parser.print_help()
    sys.exit(1)
    
if command.opts.infile:
    infile=file(command.opts.infile)
else:
    infile=sys.stdin
if command.opts.outfile:
    outfile=file(command.opts.outfile,"w")
else:
    outfile=sys.stdout
ad_rspec = RSpec(infile)
nodes = file(command.opts.nodefile).read().split()
version_manager = VersionManager()
try:
    type = ad_rspec.version.type
    version_num = ad_rspec.version.version
    request_version = version_manager._get_version(type, version_num, 'request')    
    request_rspec = RSpec(version=request_version)
    request_rspec.version.merge(ad_rspec)
    request_rspec.version.add_slivers(nodes)
except:
    logger.log_exc("sfiAddSliver failed with nodes %s" % nodes)
    sys.exit(1)
print >>outfile, request_rspec.toxml()
sys.exit(0)
