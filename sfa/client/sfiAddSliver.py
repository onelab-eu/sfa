#! /usr/bin/env python

import sys
from sfa.client.sfi_commands import Commands
from sfa.rspecs.rspec import RSpec
from sfa.rspecs.version_manager import VersionManager

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
request_rspec = RSpec(infile)
nodes = file(command.opts.nodefile).read().split()
version_manager = VersionManager()
try:
    type = request_rspec.version.type
    version_num = request_rspec.version.version
    manifest_version = version_manager._get_version(type, version_num, 'manifest')    
    manifest_rspec = RSpec(version=manifest_version)
    slivers = [{'hostname': node} for node in nodes]
    manifest_rspec.version.merge(request_rspec)
    manifest_rspec.version.add_slivers(slivers)
except:
    print >> sys.stderr, "FAILED: %s" % nodes
    sys.exit(1)
print >>outfile, manifest_rspec.toxml()
sys.exit(0)
