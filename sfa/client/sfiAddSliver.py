#! /usr/bin/env python

import sys
from sfa.util.rspecHelper import RSpec, Commands

command = Commands(usage="%prog [options] node1 node2...",
                   description="Add slivers to the RSpec. " +
                   "This command reads in an RSpec and outputs a modified " +
                   "RSpec. Use this to add nodes to your slice.")
command.add_nodefile_option()
command.prep()

for node in command.nodes:
    try:
        command.rspec.add_sliver(node)
    except:
        print >> sys.stderr, "FAILED: %s" % node

print command.rspec
    

    
