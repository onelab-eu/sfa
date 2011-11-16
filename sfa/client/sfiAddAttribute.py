#! /usr/bin/env python

import sys

from sfa.util.sfalogging import logger
from sfa.client.sfi_commands import Commands
from sfa.rspecs.rspec import RSpec

logger.enable_console()
command = Commands(usage="%prog [options] [node1 node2...]",
                   description="Add sliver attributes to the RSpec. " +
                   "This command reads in an RSpec and outputs a modified " +
                   "RSpec. Use this to add attributes to individual nodes " +
                   "in your slice.  If no nodes are specified, the " +
                   "attributes will be added to ALL nodes.",
                   epilog="NOTE: Only admins can actually set these " +
                   "attributes, with the exception of --delegations")
command.add_nodefile_option()
command.add_attribute_options()
command.prep()

if command.opts.infile:
    attrs = command.get_attribute_dict()
    rspec = RSpec(command.opts.infile)
    nodes = []
    if command.opts.nodefile:
        f = open(command.opts.nodefile, "r")
        nodes = f.read().split()
        f.close()


    for name in attrs:
        print >> sys.stderr, name, attrs[name]
        for value in attrs[name]:
            if not nodes:
                try:
                    rspec.version.add_default_sliver_attribute(name, value)
                except:
                    logger.log_exc("sfiAddAttribute FAILED on all nodes: %s=%s" % (name, value))
            else:
                for node in nodes:
                    try:
                        rspec.version.add_sliver_attribute(node, name, value)
                    except:
                        logger.log_exc ("sfiAddAttribute FAILED on node %s: %s=%s" % (node, name, value))

    print rspec.toxml()
