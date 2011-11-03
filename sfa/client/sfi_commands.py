#! /usr/bin/env python

import sys
from optparse import OptionParser

class Commands:
    def __init__(self, usage, description, epilog=None):
        self.parser = OptionParser(usage=usage, description=description,
                                   epilog=epilog)
        self.parser.add_option("-i", "", dest="infile", metavar="FILE",
                               help="read RSpec from FILE (default is stdin)")
        self.parser.add_option("-o", "", dest="outfile", metavar="FILE",
                               help="write output to FILE (default is stdout)")
        self.nodefile = False
        self.linkfile = False
        self.attributes = {}

    def add_nodefile_option(self):
        self.nodefile = True
        self.parser.add_option("-n", "", dest="nodefile", 
                               metavar="FILE",
                               help="read node list from FILE"),

    def add_linkfile_option(self):
        self.linkfile = True
        self.parser.add_option("-l", "", dest="linkfile",
                               metavar="FILE",
                               help="read link list from FILE") 

    def add_show_attributes_option(self):
        self.parser.add_option("-s", "--show-attributes", action="store_true", 
                               dest="showatt", default=False, 
                               help="show sliver attributes")

    def add_attribute_options(self):
        self.parser.add_option("", "--capabilities", action="append",
                               metavar="<cap1,cap2,...>",
                               help="Vserver bcapabilities")
        self.parser.add_option("", "--codemux", action="append",
                               metavar="<host,local-port>",
                               help="Demux HTTP between slices using " +
                               "localhost ports")
        self.parser.add_option("", "--cpu-pct", action="append",
                               metavar="<num>", 
                               help="Reserved CPU percent (e.g., 25)")
        self.parser.add_option("", "--cpu-share", action="append",
                               metavar="<num>", 
                               help="Number of CPU shares (e.g., 5)")
        self.parser.add_option("", "--delegations", 
                               metavar="<slice1,slice2,...>", action="append",
                               help="List of slices with delegation authority")
        self.parser.add_option("", "--disk-max", 
                               metavar="<num>", action="append",
                               help="Disk quota (1k disk blocks)")
        self.parser.add_option("", "--initscript", 
                               metavar="<name>", action="append",
                               help="Slice initialization script (e.g., stork)")
        self.parser.add_option("", "--ip-addresses", action="append",
                               metavar="<IP addr>", 
                               help="Add an IP address to a sliver")
        self.parser.add_option("", "--net-i2-max-kbyte", 
                               metavar="<KBytes>", action="append",
                               help="Maximum daily network Tx limit " +
                               "to I2 hosts.")
        self.parser.add_option("", "--net-i2-max-rate", 
                               metavar="<Kbps>", action="append",
                               help="Maximum bandwidth over I2 routes")
        self.parser.add_option("", "--net-i2-min-rate", 
                               metavar="<Kbps>", action="append",
                               help="Minimum bandwidth over I2 routes")
        self.parser.add_option("", "--net-i2-share", 
                               metavar="<num>", action="append",
                               help="Number of bandwidth shares over I2 routes")
        self.parser.add_option("", "--net-i2-thresh-kbyte", 
                               metavar="<KBytes>", action="append",
                               help="Limit sent to I2 hosts before warning, " +
                               "throttling")
        self.parser.add_option("", "--net-max-kbyte", 
                               metavar="<KBytes>", action="append",
                               help="Maximum daily network Tx limit " +
                               "to non-I2 hosts.")
        self.parser.add_option("", "--net-max-rate", 
                               metavar="<Kbps>", action="append",
                               help="Maximum bandwidth over non-I2 routes")
        self.parser.add_option("", "--net-min-rate", 
                               metavar="<Kbps>", action="append",
                               help="Minimum bandwidth over non-I2 routes")
        self.parser.add_option("", "--net-share", 
                               metavar="<num>", action="append",
                               help="Number of bandwidth shares over non-I2 " +
                               "routes")
        self.parser.add_option("", "--net-thresh-kbyte", 
                               metavar="<KBytes>", action="append",
                               help="Limit sent to non-I2 hosts before " +
                               "warning, throttling")
        self.parser.add_option("", "--vsys", 
                               metavar="<name>", action="append",
                               help="Vsys script (e.g., fd_fusemount)")
        self.parser.add_option("", "--vsys-vnet", 
                               metavar="<IP network>", action="append",
                               help="Allocate a virtual private network")

    def get_attribute_dict(self):
        attrlist = ['capabilities','codemux','cpu_pct','cpu_share',
                    'delegations','disk_max','initscript','ip_addresses',
                    'net_i2_max_kbyte','net_i2_max_rate','net_i2_min_rate',
                    'net_i2_share','net_i2_thresh_kbyte',
                    'net_max_kbyte','net_max_rate','net_min_rate',
                    'net_share','net_thresh_kbyte',
                    'vsys','vsys_vnet']
        attrdict = {}
        for attr in attrlist:
            value = getattr(self.opts, attr, None)
            if value is not None:
                attrdict[attr] = value
        return attrdict

    def prep(self):
        (self.opts, self.args) = self.parser.parse_args()

        #if self.opts.infile:
        #    sys.stdin = open(self.opts.infile, "r")
        #xml = sys.stdin.read()
        #self.rspec = RSpec(xml)
        #    
        #if self.nodefile:
        #    if self.opts.nodefile:
        #        f = open(self.opts.nodefile, "r")
        #        self.nodes = f.read().split()
        #        f.close()
        #    else:
        #        self.nodes = self.args
        #
        #if self.opts.outfile:
        #    sys.stdout = open(self.opts.outfile, "w")







