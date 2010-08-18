#! /usr/bin/env python

import sys
from lxml import etree
from StringIO import StringIO
from optparse import OptionParser


def merge_rspecs(rspecs):
    """
    Merge merge a list of RSpecs into 1 RSpec, and return the result.
    rspecs must be a valid RSpec string or list of RSpec strings.
    """
    if not rspecs or not isinstance(rspecs, list):
        return rspecs

    rspec = None
    for tmp_rspec in rspecs:
        try:
            tree = etree.parse(StringIO(tmp_rspec))
        except etree.XMLSyntaxError:
            # consider failing silently here
            message = str(agg_rspec) + ": " + str(sys.exc_info()[1])
            raise InvalidRSpec(message)

        root = tree.getroot()
        if root.get("type") in ["SFA"]:
            if rspec == None:
                rspec = root
            else:
                for network in root.iterfind("./network"):
                    rspec.append(deepcopy(network))
                for request in root.iterfind("./request"):
                    rspec.append(deepcopy(request))
    return etree.tostring(rspec, xml_declaration=True, pretty_print=True)

class RSpec:
    def __init__(self, xml):
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(StringIO(xml), parser)
        self.rspec = tree.getroot()

    def get_node_element(self, hostname):
        names = self.rspec.iterfind("./network/site/node/hostname")
        for name in names:
            if name.text == hostname:
                return name.getparent()
        return None
        
    def get_node_list(self):
        result = self.rspec.xpath("./network/site/node/hostname/text()")
        return result

    def get_sliver_list(self):
        result = self.rspec.xpath("./network/site/node[sliver]/hostname/text()")
        return result

    def add_sliver(self, hostname):
        node = self.get_node_element(hostname)
        etree.SubElement(node, "sliver")

    def remove_sliver(self, hostname):
        node = self.get_node_element(hostname)
        node.remove(node.find("sliver"))

    def attributes_list(self, elem):
        opts = []
        if elem is not None:
            for e in elem:
                opts.append((e.tag, e.text))
        return opts

    def get_default_sliver_attributes(self):
        defaults = self.rspec.find(".//sliver_defaults")
        return self.attributes_list(defaults)

    def get_sliver_attributes(self, hostname):
        node = self.get_node_element(hostname)
        sliver = node.find("sliver")
        return self.attributes_list(sliver)

    def add_attribute(self, elem, name, value):
        opt = etree.SubElement(elem, name)
        opt.text = value

    def add_default_sliver_attribute(self, name, value):
        defaults = self.rspec.find(".//sliver_defaults")
        if defaults is None:
            defaults = etree.Element("sliver_defaults")
            network = self.rspec.find(".//network")
            network.insert(0, defaults)
        self.add_attribute(defaults, name, value)

    def add_sliver_attribute(self, hostname, name, value):
        node = self.get_node_element(hostname)
        sliver = node.find("sliver")
        self.add_attribute(sliver, name, value)

    def remove_attribute(self, elem, name, value):
        if elem is not None:
            opts = elem.iterfind(name)
            if opts is not None:
                for opt in opts:
                    if opt.text == value:
                        elem.remove(opt)

    def remove_default_sliver_attribute(self, name, value):
        defaults = self.rspec.find(".//sliver_defaults")
        self.remove_attribute(defaults, name, value)

    def remove_sliver_attribute(self, hostname, name, value):
        node = self.get_node_element(hostname)
        sliver = node.find("sliver")
        self.remove_attribute(sliver, name, value)

    def get_site_nodes(self, siteid):
        query = './/site[@id="%s"]/node/hostname/text()' % siteid
        result = self.rspec.xpath(query)
        return result
        
    def get_link_list(self):
        linklist = []
        links = self.rspec.iterfind(".//link")
        for link in links:
            (end1, end2) = link.get("endpoints").split()
            name = link.find("description")
            linklist.append((name.text, 
                             self.get_site_nodes(end1), 
                             self.get_site_nodes(end2)))
        return linklist

    def get_vlink_list(self):
        vlinklist = []
        vlinks = self.rspec.iterfind(".//vlink")
        for vlink in vlinks:
            endpoints = vlink.get("endpoints")
            (end1, end2) = endpoints.split()
            query = './/node[@id="%s"]/hostname/text()'
            node1 = self.rspec.xpath(query % end1)[0]
            node2 = self.rspec.xpath(query % end2)[0]
            desc = "%s <--> %s" % (node1, node2) 
            kbps = vlink.find("kbps")
            vlinklist.append((endpoints, desc, kbps.text))
        return vlinklist

    def query_links(self, fromnode, tonode):
        fromsite = fromnode.getparent()
        tosite = tonode.getparent()
        fromid = fromsite.get("id")
        toid = tosite.get("id")

        query = ".//link[@endpoints = '%s %s']" % (fromid, toid)
        results = self.rspec.xpath(query)
        if results == None:
            query = ".//link[@endpoints = '%s %s']" % (toid, fromid)
            results = self.rspec.xpath(query)
        return results

    def query_vlinks(self, endpoints):
        query = ".//vlink[@endpoints = '%s']" % endpoints
        results = self.rspec.xpath(query)
        return results
            
    
    def add_vlink(self, fromhost, tohost, kbps):
        fromnode = self.get_node_element(fromhost)
        tonode = self.get_node_element(tohost)
        links = self.query_links(fromnode, tonode)

        for link in links:
            vlink = etree.SubElement(link, "vlink")
            fromid = fromnode.get("id")
            toid = tonode.get("id")
            vlink.set("endpoints", "%s %s" % (fromid, toid))
            self.add_attribute(vlink, "kbps", kbps)
        

    def remove_vlink(self, endpoints):
        vlinks = self.query_vlinks(endpoints)
        for vlink in vlinks:
            vlink.getparent().remove(vlink)

    def toxml(self):
        return etree.tostring(self.rspec, pretty_print=True, 
                              xml_declaration=True)

    def __str__(self):
        return self.toxml()

    def save(self, filename):
        f = open(filename, "w")
        f.write(self.toxml())
        f.close()


class Commands:
    def __init__(self, usage, description, epilog=None):
        self.parser = OptionParser(usage=usage, description=description,
                                   epilog=epilog)
        self.parser.add_option("-i", "", dest="infile", metavar="FILE",
                               help="read RSpec from FILE (default is stdin)")
        self.parser.add_option("-o", "", dest="outfile", metavar="FILE",
                               help="write output to FILE (default is stdout)")
        self.nodefile = False
        self.attributes = {}

    def add_nodefile_option(self):
        self.nodefile = True
        self.parser.add_option("-n", "", dest="nodefile", 
                               metavar="FILE",
                               help="read node list from FILE"),

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

        if self.opts.infile:
            sys.stdin = open(self.opts.infile, "r")
        xml = sys.stdin.read()
        self.rspec = RSpec(xml)
            
        if self.nodefile:
            if self.opts.nodefile:
                f = open(self.opts.nodefile, "r")
                self.nodes = f.read().split()
                f.close()
            else:
                self.nodes = self.args

        if self.opts.outfile:
            sys.stdout = open(self.opts.outfile, "w")







