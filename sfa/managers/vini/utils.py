from __future__ import with_statement
import re
import socket
from sfa.util.faults import *
from sfa.managers.vini.topology import PhysicalLinks
from xmlbuilder import XMLBuilder
from lxml import etree
import sys
from StringIO import StringIO

VINI_RELAXNG_SCHEMA = "/var/www/html/schemas/vini.rng"

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


class Node:
    def __init__(self, node, bps = 1000 * 1000000):
        self.id = node['node_id']
        self.idtag = "n%s" % self.id
        self.hostname = node['hostname']
        self.name = self.shortname = self.hostname.replace('.vini-veritas.net', '')
        self.site_id = node['site_id']
        self.ipaddr = socket.gethostbyname(self.hostname)
        self.bps = bps
        self.links = set()
        self.sliver = False

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
        
    def get_site(self, sites):
        return sites[self.site_id]
    
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
        return (remote.id, remote.ipaddr, bw, my_ip, remote_ip, net)
        
    def add_link(self, link):
        self.links.add(link)
        
    def add_tag(self, sites):
        s = self.get_site(sites)
        words = self.hostname.split(".")
        index = words[0].replace("node", "")
        if index.isdigit():
            self.tag = s.tag + index
        else:
            self.tag = None

    # Assumes there is at most one Link between two sites
    def get_sitelink(self, node, sites):
        site1 = sites[self.site_id]
        site2 = sites[node.site_id]
        sl = site1.links.intersection(site2.links)
        if len(sl):
            return sl.pop()
        return None

    def add_sliver(self):
        self.sliver = True

    def toxml(self, xml, hrn):
        if not self.tag:
            return
        with xml.node(id = self.idtag):
            with xml.hostname:
                xml << self.hostname
            with xml.kbps:
                xml << str(int(self.bps/1000))
            if self.sliver:
                with xml.sliver:
                    pass
    

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
            element = xml.vlink(endpoints=end_ids)
        else:
            element = xml.link(endpoints=end_ids)

        with element:
            with xml.description:
                xml << "%s -- %s" % (self.end1.name, self.end2.name)
            with xml.kbps:
                xml << str(int(self.bps/1000))
            for child in self.children:
                child.toxml(xml)
        

class Site:
    def __init__(self, site):
        self.id = site['site_id']
        self.idtag = "s%s" % self.id
        self.node_ids = site['node_ids']
        self.name = site['abbreviated_name'].replace(" ", "_")
        self.tag = site['login_base']
        self.public = site['is_public']
        self.enabled = site['enabled']
        self.links = set()

    def get_sitenodes(self, nodes):
        n = []
        for i in self.node_ids:
            n.append(nodes[i])
        return n
    
    def add_link(self, link):
        self.links.add(link)

    def toxml(self, xml, hrn, nodes):
        if not (self.public and self.enabled and self.node_ids):
            return
        with xml.site(id = self.idtag):
            with xml.name:
                xml << self.name
                
            for node in self.get_sitenodes(nodes):
                node.toxml(xml, hrn)
   
    
class Slice:
    def __init__(self, slice):
        self.id = slice['slice_id']
        self.name = slice['name']
        self.node_ids = set(slice['node_ids'])
        self.slice_tag_ids = slice['slice_tag_ids']
    
    def get_tag(self, tagname, slicetags, node = None):
        for i in self.slice_tag_ids:
            tag = slicetags[i]
            if tag.tagname == tagname:
                if (not node) or (node.id == tag.node_id):
                    return tag
        else:
            return None
        
    def get_nodes(self, nodes):
        n = []
        for id in self.node_ids:
            n.append(nodes[id])
        return n
             
    
    # Add a new slice tag   
    def add_tag(self, tagname, value, slicetags, node = None):
        record = {'slice_tag_id':None, 'slice_id':self.id, 'tagname':tagname, 'value':value}
        if node:
            record['node_id'] = node.id
        else:
            record['node_id'] = None
        tag = Slicetag(record)
        slicetags[tag.id] = tag
        self.slice_tag_ids.append(tag.id)
        tag.changed = True       
        tag.updated = True
        return tag
    
    # Update a slice tag if it exists, else add it             
    def update_tag(self, tagname, value, slicetags, node = None):
        tag = self.get_tag(tagname, slicetags, node)
        if tag and tag.value == value:
            value = "no change"
        elif tag:
            tag.value = value
            tag.changed = True
        else:
            tag = self.add_tag(tagname, value, slicetags, node)
        tag.updated = True
            
    def assign_egre_key(self, slicetags):
        if not self.get_tag('egre_key', slicetags):
            try:
                key = free_egre_key(slicetags)
                self.update_tag('egre_key', key, slicetags)
            except:
                # Should handle this case...
                pass
        return
            
    def turn_on_netns(self, slicetags):
        tag = self.get_tag('netns', slicetags)
        if (not tag) or (tag.value != '1'):
            self.update_tag('netns', '1', slicetags)
        return
   
    def turn_off_netns(self, slicetags):
        tag = self.get_tag('netns', slicetags)
        if tag and (tag.value != '0'):
            tag.delete()
        return
    
    def add_cap_net_admin(self, slicetags):
        tag = self.get_tag('capabilities', slicetags)
        if tag:
            caps = tag.value.split(',')
            for cap in caps:
                if cap == "CAP_NET_ADMIN":
                    return
            else:
                newcaps = "CAP_NET_ADMIN," + tag.value
                self.update_tag('capabilities', newcaps, slicetags)
        else:
            self.add_tag('capabilities', 'CAP_NET_ADMIN', slicetags)
        return
    
    def remove_cap_net_admin(self, slicetags):
        tag = self.get_tag('capabilities', slicetags)
        if tag:
            caps = tag.value.split(',')
            newcaps = []
            for cap in caps:
                if cap != "CAP_NET_ADMIN":
                    newcaps.append(cap)
            if newcaps:
                value = ','.join(newcaps)
                self.update_tag('capabilities', value, slicetags)
            else:
                tag.delete()
        return

    # Update the vsys/setup-link and vsys/setup-nat slice tags.
    def add_vsys_tags(self, slicetags):
        link = nat = False
        for i in self.slice_tag_ids:
            tag = slicetags[i]
            if tag.tagname == 'vsys':
                if tag.value == 'setup-link':
                    link = True
                elif tag.value == 'setup-nat':
                    nat = True
        if not link:
            self.add_tag('vsys', 'setup-link', slicetags)
        if not nat:
            self.add_tag('vsys', 'setup-nat', slicetags)
        return


class Slicetag:
    newid = -1 
    def __init__(self, tag):
        self.id = tag['slice_tag_id']
        if not self.id:
            # Make one up for the time being...
            self.id = Slicetag.newid
            Slicetag.newid -= 1
        self.slice_id = tag['slice_id']
        self.tagname = tag['tagname']
        self.value = tag['value']
        self.node_id = tag['node_id']
        self.updated = False
        self.changed = False
        self.deleted = False
    
    # Mark a tag as deleted
    def delete(self):
        self.deleted = True
        self.updated = True
    
    def write(self, api):
        if self.changed:
            if int(self.id) > 0:
                api.driver.UpdateSliceTag(self.id, self.value)
            else:
                api.driver.AddSliceTag(self.slice_id, self.tagname, self.value, self.node_id)
        elif self.deleted and int(self.id) > 0:
            api.driver.DeleteSliceTag(self.id)


"""
A topology is a compound object consisting of:
* a dictionary mapping site IDs to Site objects
* a dictionary mapping node IDs to Node objects
* the Site objects are connected via SiteLink objects representing
  the physical topology and available bandwidth
* the Node objects are connected via Link objects representing
  the requested or assigned virtual topology of a slice
"""
class Topology:
    def __init__(self, api):
        self.api = api
        self.sites = get_sites(api)
        self.nodes = get_nodes(api)
        self.tags = get_slice_tags(api)
        self.sitelinks = []
        self.nodelinks = []
    
        for (s1, s2) in PhysicalLinks:
            self.sitelinks.append(Link(self.sites[s1], self.sites[s2]))
        
        for id in self.nodes:
            self.nodes[id].add_tag(self.sites)
        
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
                            sl = node1.get_sitelink(node2, self.sites)
                            sl.bps -= allocbps
                    except:
                        pass

    
    """ Lookup site based on id or idtag value """
    def lookupSite(self, id):
        val = None
        if isinstance(id, basestring):
            id = int(id.lstrip('s'))
        try:
            val = self.sites[id]
        except:
            raise KeyError("site ID %s not found" % id)
        return val
    
    def getSites(self):
        sites = []
        for s in self.sites:
            sites.append(self.sites[s])
        return sites
        
    """ Lookup node based on id or idtag value """
    def lookupNode(self, id):
        val = None
        if isinstance(id, basestring):
            id = int(id.lstrip('n'))
        try:
            val = self.nodes[id]
        except:
            raise KeyError("node ID %s not found" % id)
        return val
    
    def getNodes(self):
        nodes = []
        for n in self.nodes:
            nodes.append(self.nodes[n])
        return nodes
    
    def nodesInTopo(self):
        nodes = []
        for n in self.nodes:
            node = self.nodes[n]
            if node.sliver:
                nodes.append(node)
        return nodes
            
    def lookupSliceTag(self, id):
        val = None
        try:
            val = self.tags[id]
        except:
            raise KeyError("slicetag ID %s not found" % id)
        return val
    
    def getSliceTags(self):
        tags = []
        for t in self.tags:
            tags.append(self.tags[t])
        return tags
    
    def lookupSiteLink(self, node1, node2):
        site1 = self.sites[node1.site_id]
        site2 = self.sites[node2.site_id]
        for link in self.sitelinks:
            if site1 == link.end1 and site2 == link.end2:
                return link
            if site2 == link.end1 and site1 == link.end2:
                return link
        return None
    

    def __add_vlink(self, vlink, slicenodes, parent = None):
        n1 = n2 = None
        endpoints = vlink.get("endpoints")
        if endpoints:
            (end1, end2) = endpoints.split()
            n1 = self.lookupNode(end1)
            n2 = self.lookupNode(end2)
        elif parent:
            """ Try to infer the endpoints for the virtual link """
            site_endpoints = parent.get("endpoints")
            (n1, n2) = self.__infer_endpoints(site_endpoints, slicenodes)
        else:
            raise Error("no endpoints given")

        #print "Added virtual link: %s -- %s" % (n1.tag, n2.tag)
        bps = int(vlink.findtext("kbps")) * 1000
        sitelink = self.lookupSiteLink(n1, n2)
        if not sitelink:
            raise PermissionError("nodes %s and %s not adjacent" % 
                                  (n1.idtag, n2.idtag))
        self.nodelinks.append(Link(n1, n2, bps, sitelink))
        return

    """ 
    Infer the endpoints of the virtual link.  If the slice exists on 
    only a single node at each end of the physical link, we'll assume that
    the user wants the virtual link to terminate at these nodes.
    """
    def __infer_endpoints(self, endpoints, slicenodes):
        n = []
        ends = endpoints.split()
        for end in ends:
            found = 0
            site = self.lookupSite(end)
            for id in site.node_ids:
                if id in slicenodes:
                    n.append(slicenodes[id])
                    found += 1
            if found != 1:
                raise Error("could not infer endpoint for site %s" % site.id)
        #print "Inferred endpoints: %s %s" % (n[0].idtag, n[1].idtag)
        return n
        
    def nodeTopoFromRSpec(self, xml):
        if self.nodelinks:
            raise Error("virtual topology already present")
            
        nodedict = {}
        for node in self.getNodes():
            nodedict[node.idtag] = node
            
        slicenodes = {}

        tree = etree.parse(StringIO(xml))

        # Validate the incoming request against the RelaxNG schema
        relaxng_doc = etree.parse(VINI_RELAXNG_SCHEMA)
        relaxng = etree.RelaxNG(relaxng_doc)
        
        if not relaxng(tree):
            error = relaxng.error_log.last_error
            message = "%s (line %s)" % (error.message, error.line)
            raise InvalidRSpec(message)

        rspec = tree.getroot()

        """
        Handle requests where the user has annotated a description of the
        physical resources (nodes and links) with virtual ones (slivers
        and vlinks).
        """
        # Find slivers under node elements
        for sliver in rspec.iterfind("./network/site/node/sliver"):
            elem = sliver.getparent()
            node = nodedict[elem.get("id")]
            slicenodes[node.id] = node
            node.add_sliver()

        # Find vlinks under link elements
        for vlink in rspec.iterfind("./network/link/vlink"):
            link = vlink.getparent()
            self.__add_vlink(vlink, slicenodes, link)

        """
        Handle requests where the user has listed the virtual resources only
        """
        # Find slivers that specify nodeid
        for sliver in rspec.iterfind("./request/sliver[@nodeid]"):
            node = nodedict[sliver.get("nodeid")]
            slicenodes[node.id] = node
            node.add_sliver()

        # Find vlinks that specify endpoints
        for vlink in rspec.iterfind("./request/vlink[@endpoints]"):
            self.__add_vlink(vlink, slicenodes)

        return

    def nodeTopoFromSliceTags(self, slice):
        if self.nodelinks:
            raise Error("virtual topology already present")
            
        for node in slice.get_nodes(self.nodes):
            node.sliver = True
            linktag = slice.get_tag('topo_rspec', self.tags, node)
            if linktag:
                l = eval(linktag.value)
                for (id, realip, bw, lvip, rvip, vnet) in l:
                    if node.id < id:
                        bps = get_tc_rate(bw)
                        remote = self.lookupNode(id)
                        sitelink = self.lookupSiteLink(node, remote)
                        self.nodelinks.append(Link(node,remote,bps,sitelink))

    def updateSliceTags(self, slice):
        if not self.nodelinks:
            return
 
        slice.update_tag('vini_topo', 'manual', self.tags)
        slice.assign_egre_key(self.tags)
        slice.turn_on_netns(self.tags)
        slice.add_cap_net_admin(self.tags)

        for node in slice.get_nodes(self.nodes):
            linkdesc = []
            for link in node.links:
                linkdesc.append(node.get_topo_rspec(link))
            if linkdesc:
                topo_str = "%s" % linkdesc
                slice.update_tag('topo_rspec', topo_str, self.tags, node)

        # Update slice tags in database
        for tag in self.getSliceTags():
            if tag.slice_id == slice.id:
                if tag.tagname == 'topo_rspec' and not tag.updated:
                    tag.delete()
                tag.write(self.api)
                
    """
    Check the requested topology against the available topology and capacity
    """
    def verifyNodeTopo(self, hrn, topo):
        for link in self.nodelinks:
            if link.bps <= 0:
                raise GeniInvalidArgument(bw, "BW")
                
            n1 = link.end1
            n2 = link.end2
            sitelink = self.lookupSiteLink(n1, n2)
            if not sitelink:
                raise PermissionError("%s: nodes %s and %s not adjacent" % (hrn, n1.tag, n2.tag))
            if sitelink.bps < link.bps:
                raise PermissionError("%s: insufficient capacity between %s and %s" % (hrn, n1.tag, n2.tag))
                
    """
    Produce XML directly from the topology specification.
    """
    def toxml(self, hrn = None):
        xml = XMLBuilder(format = True, tab_step = "  ")
        with xml.RSpec(type="VINI"):
            if hrn:
                element = xml.network(name="Public_VINI", slice=hrn)
            else:
                element = xml.network(name="Public_VINI")
                
            with element:
                for site in self.getSites():
                    site.toxml(xml, hrn, self.nodes)
                for link in self.sitelinks:
                    link.toxml(xml)

        header = '<?xml version="1.0"?>\n'
        return header + str(xml)

"""
Create a dictionary of site objects keyed by site ID
"""
def get_sites(api):
    tmp = []
    for site in api.driver.GetSites():
        t = site['site_id'], Site(site)
        tmp.append(t)
    return dict(tmp)


"""
Create a dictionary of node objects keyed by node ID
"""
def get_nodes(api):
    tmp = []
    for node in api.driver.GetNodes():
        t = node['node_id'], Node(node)
        tmp.append(t)
    return dict(tmp)

"""
Create a dictionary of slice objects keyed by slice ID
"""
def get_slice(api, slicename):
    slice = api.driver.GetSlices([slicename])
    if slice:
        return Slice(slice[0])
    else:
        return None

"""
Create a dictionary of slicetag objects keyed by slice tag ID
"""
def get_slice_tags(api):
    tmp = []
    for tag in api.driver.GetSliceTags():
        t = tag['slice_tag_id'], Slicetag(tag)
        tmp.append(t)
    return dict(tmp)
    
"""
Find a free EGRE key
"""
def free_egre_key(slicetags):
    used = set()
    for i in slicetags:
        tag = slicetags[i]
        if tag.tagname == 'egre_key':
            used.add(int(tag.value))
                
    for i in range(1, 256):
        if i not in used:
            key = i
            break
    else:
        raise KeyError("No more EGRE keys available")
        
    return "%s" % key
   
