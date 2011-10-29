#! /usr/bin/env python

import sys
from sfa.client.sfi_commands import Commands
from sfa.rspecs.rspec import RSpec
from sfa.rspecs.version_manager import VersionManager

command = Commands(usage="%prog [options] node1 node2...",
                   description="Add links to the RSpec. " +
                   "This command reads in an RSpec and outputs a modified " +
                   "RSpec. Use this to add links to your slivers")
command.add_linkfile_option()
command.prep()

if not command.opts.linkfile:
    print "Missing link list -- exiting"
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
links = file(command.opts.linkfile).read().split('\n')
link_tuples = map(lambda x: tuple(x.split()), links)

version_manager = VersionManager()
try:
    type = ad_rspec.version.type
    version_num = ad_rspec.version.version
    request_version = version_manager._get_version(type, version_num, 'request')    
    request_rspec = RSpec(version=request_version)
    request_rspec.version.merge(ad_rspec)
    request_rspec.version.add_link_requests(link_tuples)
except:
    print >> sys.stderr, "FAILED: %s" % links
    raise
    sys.exit(1)
print >>outfile, request_rspec.toxml()
sys.exit(0)
