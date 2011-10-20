#! /usr/bin/env python

import sys
from sfa.client.sfi_commands import Commands
from sfa.rspecs.rspec import RSpec

command = Commands(usage="%prog [options]",
                   description="List all slivers in the RSpec. " + 
                   "Use this to display the list of nodes belonging to " + 
                   "the slice.")
command.add_show_attributes_option()
command.prep()

if command.opts.infile:
    rspec = RSpec(command.opts.infile)
    nodes = rspec.version.get_nodes_with_slivers()
    
    if command.opts.showatt:
        defaults = rspec.version.get_default_sliver_attributes()
        if defaults:
            print "ALL NODES"
            for (name, value) in defaults:
                print "  %s: %s" % (name, value)        

    for node in nodes:
        print node
        if command.opts.showatt:
            atts = rspec.version.get_sliver_attributes(node)
            for (name, value) in atts:
                print "  %s: %s" % (name, value)

    
