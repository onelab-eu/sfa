from __future__ import with_statement
from sfa.util.faults import *
from xmlbuilder import XMLBuilder
from lxml import etree
import sys
from sfa.plc.network import *
from sfa.managers.vini.topology import PhysicalLinks

# Taken from bwlimit.py
#
# See tc_util.c and http://physics.nist.gov/cuu/Units/binary.html. Be
# warned that older versions of tc interpret "kbps", "mbps", "mbit",
# and "kbit" to mean (in this system) "kibps", "mibps", "mibit", and
# "kibit" and that if an older version is installed, all rates will
# be off by a small fraction.
suffixes = {
    "":         1,
    "bit":	1,
    "kibit":	1024,
    "kbit":	1000,
    "mibit":	1024*1024,
    "mbit":	1000000,
    "gibit":	1024*1024*1024,
    "gbit":	1000000000,
    "tibit":	1024*1024*1024*1024,
    "tbit":	1000000000000,
    "bps":	8,
    "kibps":	8*1024,
    "kbps":	8000,
    "mibps":	8*1024*1024,
    "mbps":	8000000,
    "gibps":	8*1024*1024*1024,
    "gbps":	8000000000,
    "tibps":	8*1024*1024*1024*1024,
    "tbps":	8000000000000
}


def get_tc_rate(s):
    """
    Parses an integer or a tc rate string (e.g., 1.5mbit) into bits/second
    """

    if type(s) == int:
        return s
    m = re.match(r"([0-9.]+)(\D*)", s)
    if m is None:
        return -1
    suffix = m.group(2).lower()
    if suffixes.has_key(suffix):
        return int(float(m.group(1)) * suffixes[suffix])
    else:
        return -1

def format_tc_rate(rate):
    """
    Formats a bits/second rate into a tc rate string
    """

    if rate >= 1000000000 and (rate % 1000000000) == 0:
        return "%.0fgbit" % (rate / 1000000000.)
    elif rate >= 1000000 and (rate % 1000000) == 0:
        return "%.0fmbit" % (rate / 1000000.)
    elif rate >= 1000:
        return "%.0fkbit" % (rate / 1000.)
    else:
        return "%.0fbit" % rate


class ViniNode(Node):
    def __init__(self, network, node, bps = 1000 * 1000000):
        Node.__init__(self, network, node)
        self.bps = bps
        self.links = set()
        self.name = self.hostname.replace('.vini-veritas.net', '')

    def get_link_id(self, remote):
        if self.id < remote.id:
            link = (self.id<<7) + remote.id
        else:
            link = (remote.id<<7) + self.id
        return link
        
    def get_iface_id(self, remote):
        if self.id < remote.id:
            iface = 1
        else:
            iface = 2
        return iface
    
    def get_virt_ip(self, remote):
        link = self.get_link_id(remote)
        iface = self.get_iface_id(remote)
        first = link >> 6
        second = ((link & 0x3f)<<2) + iface
        return "192.168.%d.%d" % (first, second)

    def get_virt_net(self, remote):
        link = self.get_link_id(remote)
        first = link >> 6
        second = (link & 0x3f)<<2
        return "192.168.%d.%d/30" % (first, second)
        
    def get_topo_rspec(self, link):
        if link.end1 == self:
            remote = link.end2
        elif link.end2 == self:
            remote = link.end1
        else:
            raise Error("Link does not connect to Node")
            
        my_ip = self.get_virt_ip(remote)
        remote_ip = remote.get_virt_ip(self)
        net = self.get_virt_net(remote)
        bw = format_tc_rate(link.bps)
        ipaddr = remote.get_primary_iface().ipv4
        return (remote.id, ipaddr, bw, my_ip, remote_ip, net)
        
    def add_link(self, link):
        self.links.add(link)
        
    # Assumes there is at most one Link between two sites
    def get_sitelink(self, node):
        site1 = self.network.sites[self.site_id]
        site2 = self.network.sites[node.site_id]
        sl = site1.links.intersection(site2.links)
        if len(sl):
            return sl.pop()
        return None

    def toxml(self, xml):
        slice = self.network.slice
        if self.whitelist and not self.sliver:
            if not slice or slice.id not in self.whitelist:
                return

        with xml.node(id = self.idtag):
            with xml.hostname:
                xml << self.hostname
            with xml.bw_unallocated(units="kbps"):
                xml << str(int(self.bps/1000))
            self.get_primary_iface().toxml(xml)
            if self.sliver:
                self.sliver.toxml(xml)


class ViniSite(Site):
    def __init__(self, network, site):
        Site.__init__(self, network, site)
        self.links = set()

    def add_link(self, link):
        self.links.add(link)

class ViniSlice(Slice):
    def assign_egre_key(self):
        tag = self.get_tag('egre_key')
        if not tag:
            try:
                key = self.network.free_egre_key()
            except:
                raise InvalidRSpec("ran out of EGRE keys!")
            tag = self.update_tag('egre_key', key, None, 'admin')
        return
            
    def turn_on_netns(self):
        tag = self.get_tag('netns')
        if (not tag) or (tag.value != '1'):
            tag = self.update_tag('netns', '1', None, 'admin')
        return
   
    def turn_off_netns(self):
        tag = self.get_tag('netns')
        if tag and (tag.value != '0'):
            tag.delete()
        return
    
    def add_cap_net_admin(self):
        tag = self.get_tag('capabilities')
        if tag:
            caps = tag.value.split(',')
            for cap in caps:
                if cap == "CAP_NET_ADMIN":
                    newcaps = tag.value
                    break
            else:
                newcaps = "CAP_NET_ADMIN," + tag.value
            self.update_tag('capabilities', newcaps, None, 'admin')
        else:
            tag = self.add_tag('capabilities', 'CAP_NET_ADMIN', None, 'admin')
        return
    
    def remove_cap_net_admin(self):
        tag = self.get_tag('capabilities')
        if tag:
            caps = tag.value.split(',')
            newcaps = []
            for cap in caps:
                if cap != "CAP_NET_ADMIN":
                    newcaps.append(cap)
            if newcaps:
                value = ','.join(newcaps)
                self.update_tag('capabilities', value, None, 'admin')
            else:
                tag.delete()
        return

class Link:
    def __init__(self, end1, end2, bps = 1000 * 1000000, parent = None):
        self.end1 = end1
        self.end2 = end2
        self.bps = bps
        self.parent = parent
        self.children = []

        end1.add_link(self)
        end2.add_link(self)
        
        if self.parent:
            self.parent.children.append(self)
            
    def toxml(self, xml):
        end_ids = "%s %s" % (self.end1.idtag, self.end2.idtag)

        if self.parent:
            with  xml.vlink(endpoints=end_ids):
                with xml.description:
                    xml << "%s -- %s" % (self.end1.name, self.end2.name)
                with xml.kbps:
                    xml << str(int(self.bps/1000))
        else:
            with xml.link(endpoints=end_ids):
                with xml.description:
                    xml << "%s -- %s" % (self.end1.name, self.end2.name)
                with xml.bw_unallocated(units="kbps"):
                    xml << str(int(self.bps/1000))
                for child in self.children:
                    child.toxml(xml)
        


class ViniNetwork(Network):
    def __init__(self, api, type = "SFA"):
        Network.__init__(self, api, type)
        self.sitelinks = []
        self.nodelinks = []
    
        for (s1, s2) in PhysicalLinks:
            self.sitelinks.append(Link(self.sites[s1], self.sites[s2]))
        
        for t in self.tags:
            tag = self.tags[t]
            if tag.tagname == 'topo_rspec':
                node1 = self.nodes[tag.node_id]
                l = eval(tag.value)
                for (id, realip, bw, lvip, rvip, vnet) in l:
                    allocbps = get_tc_rate(bw)
                    node1.bps -= allocbps
                    try:
                        node2 = self.nodes[id]
                        if node1.id < node2.id:
                            sl = node1.get_sitelink(node2)
                            sl.bps -= allocbps
                    except:
                        pass

    def lookupSiteLink(self, node1, node2):
        site1 = self.sites[node1.site_id]
        site2 = self.sites[node2.site_id]
        for link in self.sitelinks:
            if site1 == link.end1 and site2 == link.end2:
                return link
            if site2 == link.end1 and site1 == link.end2:
                return link
        return None
    

    """
    Check the requested topology against the available topology and capacity
    """
    def verifyTopology(self):
        for link in self.nodelinks:
            if link.bps <= 0:
                raise InvalidRSpec("must request positive bandwidth")
                
            n1 = link.end1
            n2 = link.end2
            sitelink = self.lookupSiteLink(n1, n2)
            if not sitelink:
                raise InvalidRSpec("nodes %s and %s are not adjacent" % 
                                   (n1.idtag, n2.idtag))
            if sitelink.bps < link.bps:
                raise InvalidRSpec("not enough capacity between %s and %s" % 
                                   (n1.idtag, n2.idtag))
                
    def __add_vlink(self, vlink, parent = None):
        n1 = n2 = None
        endpoints = vlink.get("endpoints")
        if endpoints:
            (end1, end2) = endpoints.split()
            n1 = self.lookupNode(end1)
            n2 = self.lookupNode(end2)
        elif parent:
            """ Try to infer the endpoints for the virtual link """
            site_endpoints = parent.get("endpoints")
            (n1, n2) = self.__infer_endpoints(site_endpoints)
        else:
            raise InvalidRSpec("no endpoints given")

        #print "Added virtual link: %s -- %s" % (n1.tag, n2.tag)
        bps = int(vlink.findtext("kbps")) * 1000
        sitelink = self.lookupSiteLink(n1, n2)
        if not sitelink:
            raise InvalidRSpec("nodes %s and %s are not adjacent" % 
                                  (n1.idtag, n2.idtag))
        self.nodelinks.append(Link(n1, n2, bps, sitelink))
        return

    """ 
    Infer the endpoints of the virtual link.  If the slice exists on 
    only a single node at each end of the physical link, we'll assume that
    the user wants the virtual link to terminate at these nodes.
    """
    def __infer_endpoints(self, endpoints):
        n = []
        ends = endpoints.split()
        for end in ends:
            found = 0
            site = self.lookupSite(end)
            for id in site.node_ids:
                if id in self.nodedict:
                    n.append(self.nodedict[id])
                    found += 1
            if found != 1:
                raise InvalidRSpec("could not infer endpoint for site %s" % 
                                   site.idtag)
        #print "Inferred endpoints: %s %s" % (n[0].idtag, n[1].idtag)
        return n
        
    def addRSpec(self, xml, schema = None):
        Network.addRSpec(self, xml, schema)
        self.nodedict = {}
        for node in self.nodesWithSlivers():
            self.nodedict[node.id] = node
        
        # Find vlinks under link elements
        for vlink in self.rspec.iterfind("./network/link/vlink"):
            link = vlink.getparent()
            self.__add_vlink(vlink, link)

        # Find vlinks that specify endpoints
        for vlink in self.rspec.iterfind("./request/vlink[@endpoints]"):
            self.__add_vlink(vlink)


    def addSlice(self):
        Network.addSlice(self)

        for node in self.slice.get_nodes():
            linktag = self.slice.get_tag('topo_rspec', node)
            if linktag:
                l = eval(linktag.value)
                for (id, realip, bw, lvip, rvip, vnet) in l:
                    if node.id < id:
                        bps = get_tc_rate(bw)
                        remote = self.lookupNode(id)
                        sitelink = self.lookupSiteLink(node, remote)
                        self.nodelinks.append(Link(node,remote,bps,sitelink))


    def updateSliceTags(self):
        slice = self.slice

        tag = slice.update_tag('vini_topo', 'manual', None, 'admin')
        slice.assign_egre_key()
        slice.turn_on_netns()
        slice.add_cap_net_admin()

        for node in self.nodesWithSlivers():
            linkdesc = []
            for link in node.links:
                linkdesc.append(node.get_topo_rspec(link))
            if linkdesc:
                topo_str = "%s" % linkdesc
                tag = slice.update_tag('topo_rspec', topo_str, node, 'admin')

        # Expire the un-updated topo_rspec tags
        for tag in self.getSliceTags():
            if tag.tagname in ['topo_rspec']:
                if not tag.was_updated():
                    tag.delete()

        Network.updateSliceTags(self)

    """
    Find a free EGRE key
    """
    def free_egre_key(self):
        used = set()
        for tag in self.getSliceTags():
            if tag.tagname == 'egre_key':
                used.add(int(tag.value))
                
        for i in range(1, 256):
            if i not in used:
                key = i
                break
        else:
            raise KeyError("No more EGRE keys available")
        
        return str(key)

    """
    Produce XML directly from the topology specification.
    """
    def toxml(self):
        xml = XMLBuilder(format = True, tab_step = "  ")
        with xml.RSpec(type=self.type):
            if self.slice:
                element = xml.network(name=self.api.hrn, slice=self.slice.hrn)
            else:
                element = xml.network(name=self.api.hrn)

            with element:
                if self.slice:
                    self.slice.toxml(xml)
                for site in self.getSites():
                    site.toxml(xml)
                for link in self.sitelinks:
                    link.toxml(xml)

        header = '<?xml version="1.0"?>\n'
        return header + str(xml)

    """
    Create a dictionary of ViniSite objects keyed by site ID
    """
    def get_sites(self, api):
        tmp = []
        for site in api.driver.GetSites({'peer_id': None}):
            t = site['site_id'], ViniSite(self, site)
            tmp.append(t)
        return dict(tmp)


    """
    Create a dictionary of ViniNode objects keyed by node ID
    """
    def get_nodes(self, api):
        tmp = []
        for node in api.driver.GetNodes({'peer_id': None}):
            t = node['node_id'], ViniNode(self, node)
            tmp.append(t)
        return dict(tmp)

    """
    Return a ViniSlice object for a single slice
    """
    def get_slice(self, api, hrn):
        slicename = hrn_to_pl_slicename(hrn)
        slice = api.driver.GetSlices([slicename])
        if slice:
            self.slice = ViniSlice(self, slicename, slice[0])
            return self.slice
        else:
            return None


    
