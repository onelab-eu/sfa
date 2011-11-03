from __future__ import with_statement
import sys
import re
import socket
from StringIO import StringIO
from lxml import etree
from xmlbuilder import XMLBuilder

from sfa.util.faults import InvalidRSpec
from sfa.util.xrn import get_authority
from sfa.util.plxrn import hrn_to_pl_slicename, hostname_to_urn

class Sliver:
    def __init__(self, node):
        self.node = node
        self.network = node.network
        self.slice = node.network.slice
        
    def toxml(self, xml):
        with xml.sliver:
            self.slice.tags_to_xml(xml, self.node)

        
class Iface:
    def __init__(self, network, iface):
        self.network = network
        self.id = iface['interface_id']
        self.idtag = "i%s" % self.id
        self.ipv4 = iface['ip']
        self.bwlimit = iface['bwlimit']
        self.hostname = iface['hostname']
        self.primary = iface['is_primary']

    def toxml(self, xml):
        """
        Just print out bwlimit right now
        """
        if self.bwlimit:
            with xml.bw_limit(units="kbps"):
                xml << str(self.bwlimit / 1000)


class Node:
    def __init__(self, network, node):
        self.network = network
        self.id = node['node_id']
        self.idtag = "n%s" % self.id
        self.hostname = node['hostname']
        self.site_id = node['site_id']
        self.iface_ids = node['interface_ids']
        self.sliver = None
        self.whitelist = node['slice_ids_whitelist']
        auth = self.network.api.hrn
        login_base = self.get_site().idtag
        self.urn = hostname_to_urn(auth, login_base, self.hostname)

    def get_primary_iface(self):
        for id in self.iface_ids:
            iface = self.network.lookupIface(id)
            if iface.primary:
                return iface
        return None
        
    def get_site(self):
        return self.network.lookupSite(self.site_id)
    
    def add_sliver(self):
        self.sliver = Sliver(self)

    def toxml(self, xml):
        slice = self.network.slice
        if self.whitelist and not self.sliver:
            if not slice or slice.id not in self.whitelist:
                return

        with xml.node(id = self.idtag):
            with xml.hostname:
                xml << self.hostname
            with xml.urn:
                xml << self.urn
            iface = self.get_primary_iface()
            if iface:
                iface.toxml(xml)
            if self.sliver:
                self.sliver.toxml(xml)
    

class Site:
    def __init__(self, network, site):
        self.network = network
        self.id = site['site_id']
        self.node_ids = site['node_ids']
        self.node_ids.sort()
        self.name = site['abbreviated_name']
        self.tag = site['login_base']
        self.idtag = site['login_base']
        self.public = site['is_public']
        self.enabled = site['enabled']
        self.links = set()
        self.whitelist = False

    def get_sitenodes(self):
        n = []
        for i in self.node_ids:
            n.append(self.network.lookupNode(i))
        return n
    
    def toxml(self, xml):
        if not (self.public and self.enabled and self.node_ids):
            return
        with xml.site(id = self.idtag):
            with xml.name:
                xml << self.name
            for node in self.get_sitenodes():
                node.toxml(xml)
   
    
class Slice:
    def __init__(self, network, hrn, slice):
        self.hrn = hrn
        self.network = network
        self.id = slice['slice_id']
        self.name = slice['name']
        self.peer_id = slice['peer_id']
        self.node_ids = set(slice['node_ids'])
        self.slice_tag_ids = slice['slice_tag_ids']
    
    """
    Use with tags that can have more than one instance
    """
    def get_multi_tag(self, tagname, node = None):
        tags = []
        for i in self.slice_tag_ids:
            try: 
                tag = self.network.lookupSliceTag(i)                 
                if tag.tagname == tagname:
                    if node:
                        if node.id == tag.node_id:
                            tags.append(tag)
                    elif not tag.node_id:
                        tags.append(tag)
            except InvalidRSpec, e: 
                # As they're not needed, we ignore some tag types from 
                # GetSliceTags call. See Slicetag.ignore_tags 
                pass 
        return tags
        
    """
    Use with tags that have only one instance
    """
    def get_tag(self, tagname, node = None):
        for i in self.slice_tag_ids:
            try:
                tag = self.network.lookupSliceTag(i) 
                if tag.tagname == tagname: 
                    if node:
                        if node.id == tag.node_id:
                            return tag
                    elif not tag.node_id:
                        return tag 
            except InvalidRSpec, e:
                # As they're not needed, we ignore some tag types from
                # GetSliceTags call. See Slicetag.ignore_tags
                pass
        return None
        
    def get_nodes(self):
        n = []
        for id in self.node_ids:
            if id in self.network.nodes:
                n.append(self.network.nodes[id])
        return n

    # Add a new slice tag   
    def add_tag(self, tagname, value, node = None, role = "user"):
        tt = self.network.lookupTagType(tagname)
        if not tt.permit_update(role):
            raise InvalidRSpec("permission denied to modify '%s' tag" % tagname)
        tag = Slicetag()
        tag.initialize(tagname, value, node, self.network)
        self.network.tags[tag.id] = tag
        self.slice_tag_ids.append(tag.id)
        return tag
    
    # Update a slice tag if it exists, else add it             
    def update_tag(self, tagname, value, node = None, role = "user"):
        tag = self.get_tag(tagname, node)
        if tag and tag.value == value:
            return tag

        tt = self.network.lookupTagType(tagname)
        if not tt.permit_update(role):
            raise InvalidRSpec("permission denied to modify '%s' tag" % tagname)

        if tag:
            tag.change(value)
        else:
            tag = self.add_tag(tagname, value, node, role)
        return tag
            
    def update_multi_tag(self, tagname, value, node = None, role = "user"):
        tags = self.get_multi_tag(tagname, node)
        for tag in tags:
            if tag and tag.value == value:
                break
        else:
            tag = self.add_tag(tagname, value, node, role)
        return tag
            
    def tags_to_xml(self, xml, node = None):
        tagtypes = self.network.getTagTypes()
        for tt in tagtypes:
            if tt.in_rspec:
                if tt.multi:
                    tags = self.get_multi_tag(tt.tagname, node)
                    for tag in tags:
                        if not tag.was_deleted():  ### Debugging
                            xml << (tag.tagname, tag.value)
                else:
                    tag = self.get_tag(tt.tagname, node)
                    if tag:
                        if not tag.was_deleted():   ### Debugging
                            xml << (tag.tagname, tag.value)

    def toxml(self, xml):
        with xml.sliver_defaults:
            self.tags_to_xml(xml)


class Slicetag:
    newid = -1 
    filter_fields = ['slice_tag_id','slice_id','tagname','value','node_id','category'] 
    ignore_tags = ['hmac','ssh_key']
    def __init__(self, tag = None):
        if not tag:
            return
        self.id = tag['slice_tag_id']
        self.slice_id = tag['slice_id']
        self.tagname = tag['tagname']
        self.value = tag['value']
        self.node_id = tag['node_id']
        self.category = tag['category']
        self.status = None

    # Create a new slicetag that will be written to the DB later
    def initialize(self, tagname, value, node, network):
        tt = network.lookupTagType(tagname)
        self.id = Slicetag.newid
        Slicetag.newid -=1
        self.slice_id = network.slice.id
        self.tagname = tagname
        self.value = value
        if node:
            self.node_id = node.id
        else:
            self.node_id = None
        self.category = tt.category
        self.status = "new"

    def change(self, value):
        if self.value != value:
            self.value = value
            self.status = "change"
        else:
            self.status = "updated"
        
    # Mark a tag as deleted
    def delete(self):
        self.status = "delete"

    def was_added(self):
        return (self.id < 0)

    def was_changed(self):
        return (self.status == "change")

    def was_deleted(self):
        return (self.status == "delete")

    def was_updated(self):
        return (self.status != None)
    
    def write(self, api):
        if self.was_added():
            api.plshell.AddSliceTag(api.plauth, self.slice_id, 
                                    self.tagname, self.value, self.node_id)
        elif self.was_changed():
            api.plshell.UpdateSliceTag(api.plauth, self.id, self.value)
        elif self.was_deleted():
            api.plshell.DeleteSliceTag(api.plauth, self.id)


class TagType:
    ignore_tags = ['hmac','ssh_key']
    def __init__(self, tagtype):
        self.id = tagtype['tag_type_id']
        self.category = tagtype['category']
        self.tagname = tagtype['tagname']
        self.roles = tagtype['roles']
        self.multi = False
        self.in_rspec = False
        if self.category == 'slice/rspec':
            self.in_rspec = True
        if self.tagname in ['codemux', 'ip_addresses', 'vsys']:
            self.multi = True

    def permit_update(self, role):
        if role in self.roles:
            return True
        return False
        

class Network:
    """
    A Network is a compound object consisting of:
    * a dictionary mapping site IDs to Site objects
    * a dictionary mapping node IDs to Node objects
    * a dictionary mapping interface IDs to Iface objects
    """
    def __init__(self, api, type = "SFA"):
        self.api = api
        self.type = type
        self.sites = self.get_sites(api)
        self.nodes = self.get_nodes(api)
        self.ifaces = self.get_ifaces(api)
        self.tags = self.get_slice_tags(api)
        self.tagtypes = self.get_tag_types(api)
        self.slice = None
        self.sitemap = {}
        for s in self.sites:
            site = self.sites[s]
            self.sitemap[site.idtag] = site.id

    def lookupSiteIdtag(self, name):
        """ Lookup site id from name """
        val = None
        try:
            val = self.sitemap[name]
        except:
            raise InvalidRSpec("site name '%s' not found" % name)
        return val
    
    def lookupSite(self, id):
        """ Lookup site based on id or idtag value """
        val = None
        if isinstance(id, basestring):
            id = self.lookupSiteIdtag(id)
        try:
            val = self.sites[id]
        except:
            self.api.logger.error("Invalid RSpec: site ID %s not found" % id )
            raise InvalidRSpec("site ID %s not found" % id)
        return val
    
    def getSites(self):
        sites = []
        for s in self.sites:
            sites.append(self.sites[s])
        return sites
        
    def lookupNode(self, id):
        """ Lookup node based on id or idtag value """
        val = None
        if isinstance(id, basestring):
            id = int(id.lstrip('n'))
        try:
            val = self.nodes[id]
        except:
            raise InvalidRSpec("node ID %s not found" % id)
        return val
    
    def getNodes(self):
        nodes = []
        for n in self.nodes:
            nodes.append(self.nodes[n])
        return nodes
    
    def lookupIface(self, id):
        """ Lookup iface based on id or idtag value """
        val = None
        if isinstance(id, basestring):
            id = int(id.lstrip('i'))
        try:
            val = self.ifaces[id]
        except:
            raise InvalidRSpec("interface ID %s not found" % id)
        return val
    
    def getIfaces(self):
        ifaces = []
        for i in self.ifaces:
            ifaces.append(self.ifaces[i])
        return ifaces
    
    def nodesWithSlivers(self):
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
            raise InvalidRSpec("slicetag ID %s not found" % id)
        return val
    
    def getSliceTags(self):
        tags = []
        for t in self.tags:
            tags.append(self.tags[t])
        return tags
    
    def lookupTagType(self, name):
        val = None
        try:
            val = self.tagtypes[name]
        except:
            raise InvalidRSpec("tag %s not found" % name)
        return val
    
    def getTagTypes(self):
        tags = []
        for t in self.tagtypes:
            tags.append(self.tagtypes[t])
        return tags
    
    def __process_attributes(self, element, node=None):
        """
        Process the elements under <sliver_defaults> or <sliver>
        """
        if element is None:
            return 

        tagtypes = self.getTagTypes()
        for tt in tagtypes:
            if tt.in_rspec:
                if tt.multi:
                    for e in element.iterfind("./" + tt.tagname):
                        self.slice.update_multi_tag(tt.tagname, e.text, node)
                else:
                    e = element.find("./" + tt.tagname)
                    if e is not None:
                        self.slice.update_tag(tt.tagname, e.text, node)

    def addRSpec(self, xml, schema=None):
        """
        Annotate the objects in the Network with information from the RSpec
        """
        try:
            tree = etree.parse(StringIO(xml))
        except etree.XMLSyntaxError:
            message = str(sys.exc_info()[1])
            raise InvalidRSpec(message)

        # Filter out stuff that's not for us
        rspec = tree.getroot()
        for network in rspec.iterfind("./network"):
            if network.get("name") != self.api.hrn:
                rspec.remove(network)
        for request in rspec.iterfind("./request"):
            if request.get("name") != self.api.hrn:
                rspec.remove(request)

        if schema:
            # Validate the incoming request against the RelaxNG schema
            relaxng_doc = etree.parse(schema)
            relaxng = etree.RelaxNG(relaxng_doc)
        
            if not relaxng(tree):
                error = relaxng.error_log.last_error
                message = "%s (line %s)" % (error.message, error.line)
                self.api.logger.error("failed to validate rspec %r"%message)
                self.api.logger.debug("---------- XML input BEG")
                self.api.logger.debug(xml)
                self.api.logger.debug("---------- XML input END")
                raise InvalidRSpec(message)

        self.rspec = rspec

        defaults = rspec.find(".//sliver_defaults")
        self.__process_attributes(defaults)

        # Find slivers under node elements
        for sliver in rspec.iterfind("./network/site/node/sliver"):
            elem = sliver.getparent()
            try:
                node = self.lookupNode(elem.get("id"))
            except:
                # Don't worry about nodes from other aggregates
                pass
            else:
                node.add_sliver()
                self.__process_attributes(sliver, node)

        # Find slivers that specify nodeid
        for sliver in rspec.iterfind("./request/sliver[@nodeid]"):
            try:
                node = self.lookupNode(sliver.get("nodeid"))
            except:
                # Don't worry about nodes from other aggregates
                pass
            else:
                node.add_sliver()
                self.__process_attributes(sliver, node)

        return

    def addSlice(self):
        """
        Annotate the objects in the Network with information from the slice
        """
        slice = self.slice
        if not slice:
            raise InvalidRSpec("no slice associated with network")

        for node in slice.get_nodes():
            node.add_sliver()

    def updateSliceTags(self):
        """
        Write any slice tags that have been added or modified back to the DB
        """
        for tag in self.getSliceTags():
            if tag.category == 'slice/rspec' and not tag.was_updated():
                tt = self.lookupTagType(tag.tagname)
                if tt.permit_update("user"):
                    tag.delete()

        # Update slice tags in database
        for tag in self.getSliceTags():
            if tag.slice_id == self.slice.id:
                tag.write(self.api) 

    def toxml(self):
        """
        Produce XML directly from the topology specification.
        """
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

        header = '<?xml version="1.0"?>\n'
        return header + str(xml)

    def get_sites(self, api):
        """
        Create a dictionary of site objects keyed by site ID
        """
        tmp = []
        for site in api.plshell.GetSites(api.plauth, {'peer_id': None}):
            t = site['site_id'], Site(self, site)
            tmp.append(t)
        return dict(tmp)


    def get_nodes(self, api):
        """
        Create a dictionary of node objects keyed by node ID
        """
        tmp = []
        for node in api.plshell.GetNodes(api.plauth, {'peer_id': None}):
            try:
                t = node['node_id'], Node(self, node)
                tmp.append(t)
            except:
                self.api.logger.error("Failed to add node %s (%s) to RSpec" % (node['hostname'], node['node_id']))
                 
        return dict(tmp)

    def get_ifaces(self, api):
        """
        Create a dictionary of node objects keyed by node ID
        """
        tmp = []
        for iface in api.plshell.GetInterfaces(api.plauth):
            t = iface['interface_id'], Iface(self, iface)
            tmp.append(t)
        return dict(tmp)

    def get_slice_tags(self, api):
        """
        Create a dictionary of slicetag objects keyed by slice tag ID
        """
        tmp = []
        for tag in api.plshell.GetSliceTags(api.plauth, {'~tagname':Slicetag.ignore_tags}, Slicetag.filter_fields): 
            t = tag['slice_tag_id'], Slicetag(tag)
            tmp.append(t)
        return dict(tmp)
    
    def get_tag_types(self, api):
        """
        Create a list of tagtype obects keyed by tag name
        """
        tmp = []
        for tag in api.plshell.GetTagTypes(api.plauth, {'~tagname':TagType.ignore_tags}):
            t = tag['tagname'], TagType(tag)
            tmp.append(t)
        return dict(tmp)
    
    def get_slice(self, api, hrn):
        """
        Return a Slice object for a single slice
        """
        slicename = hrn_to_pl_slicename(hrn)
        slice = api.plshell.GetSlices(api.plauth, [slicename])
        if len(slice):
            self.slice = Slice(self, slicename, slice[0])
            return self.slice
        else:
            return None
    

