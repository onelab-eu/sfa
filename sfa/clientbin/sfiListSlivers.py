#! /usr/bin/env python

import sys
from sfa.client.sfi_commands import Commands

from sfa.rspecs.rspec import RSpec

from sfa.planetlab.plxrn import xrn_to_hostname

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
        hostname = None
        if node.get('component_id'):
            hostname = xrn_to_hostname(node['component_id'])
        if hostname:
            print hostname
            if command.opts.showatt:
                atts = rspec.version.get_sliver_attributes(hostname)
                for (name, value) in atts:
                    print "  %s: %s" % (name, value)

    
