#! /usr/bin/env python

import sys
from sfa.client.sfi_commands import Commands
from sfa.rspecs.rspec import RSpec
from sfa.util.xrn import Xrn 

command = Commands(usage="%prog [options]",
                   description="List all links in the RSpec. " + 
                   "Use this to display the list of available links. " ) 
command.prep()

if command.opts.infile:
    rspec = RSpec(command.opts.infile)
    links = rspec.version.get_links()
    if command.opts.outfile:
        sys.stdout = open(command.opts.outfile, 'w')
    
    for link in links:
        ifname1 = Xrn(link['interface1']['component_id']).get_leaf()
        ifname2 = Xrn(link['interface2']['component_id']).get_leaf()
        print "%s %s" % (ifname1, ifname2)



    
