#!/usr/bin/env python
# -*- coding: utf-8 -*-
from copy import deepcopy
from lxml import etree

from sfa.util.sfalogging import logger
from sfa.util.xrn import hrn_to_urn, urn_to_hrn
from sfa.rspecs.version import RSpecVersion
from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.versions.pgv2Link import PGv2Link
from sfa.rspecs.elements.versions.sfav1Node import SFAv1Node
from sfa.rspecs.elements.versions.sfav1Sliver import SFAv1Sliver
from sfa.rspecs.elements.versions.sfav1Lease import SFAv1Lease
from sfa.rspecs.elements.versions.ofeliav1datapath import Ofeliav1Datapath
from sfa.rspecs.elements.versions.ofeliav1link import Ofeliav1Link

class Ofelia(RSpecVersion):
    enabled = True
    type = 'OFELIA'
    content_type = '*'
    version = '1'
    schema = 'https://github.com/fp7-ofelia/ocf/blob/ocf.rspecs/openflow/schemas/ad.xsd'
    namespace = 'openflow'
    extensions = {}
    namespaces = dict(extensions.items() + [('default', namespace)])
    #template = '<RSpec type="%s"></RSpec>' % type
    template = '<rspec></rspec>'

    # Network 
    def get_networks(self):
        raise Exception, "Not implemented"
        network_elems = self.xml.xpath('//network')
        networks = [network_elem.get_instance(fields=['name', 'slice']) for \
                    network_elem in network_elems]
        return networks    


    def add_network(self, network):
        raise Exception, "Not implemented"
        network_tags = self.xml.xpath('//network[@name="%s"]' % network)
        if not network_tags:
            network_tag = self.xml.add_element('network', name=network)
        else:
            network_tag = network_tags[0]
        return network_tag

# These are all resources 
# get_resources function can return all resources or a specific type of resource
    def get_resources(self, filter=None, type=None):
        resources = list()
        if not type or type=='datapath':
            datapaths = self.get_datapaths(filter)
            for datapath in datapaths:
                datapath['type']='datapath'
            resources.extend(datapaths)
        if not type or type=='link':
            links = self.get_links(filter)
            for link in links:
                link['type']='link'
            resources.extend(links)
        return resources

    # Datapaths
    def get_datapaths(self, filter=None):
        return Ofeliav1Datapath.get_datapaths(self.xml, filter)

    # Links
    def get_links(self, filter=None):
        return Ofeliav1Link.get_links(self.xml, filter)

#    def get_link_requests(self):
#        return PGv2Link.get_link_requests(self.xml) 
#
#    def add_links(self, links):
#        networks = self.get_networks()
#        if len(networks) > 0:
#            xml = networks[0].element
#        else:
#            xml = self.xml
#        PGv2Link.add_links(xml, links)
#
#    def add_link_requests(self, links):
#        PGv2Link.add_link_requests(self.xml, links)



    # Slivers
   
    def add_slivers(self, hostnames, attributes=None, sliver_urn=None, append=False):
        if attributes is None: attributes=[]
        # add slice name to network tag
        network_tags = self.xml.xpath('//network')
        if network_tags:
            network_tag = network_tags[0]
            network_tag.set('slice', urn_to_hrn(sliver_urn)[0])

        # add slivers
        sliver = {'name':sliver_urn,
                  'pl_tags': attributes}
        for hostname in hostnames:
            if sliver_urn:
                sliver['name'] = sliver_urn
            node_elems = self.get_nodes({'component_id': '*%s*' % hostname})
            if not node_elems:
                continue
            node_elem = node_elems[0]
            SFAv1Sliver.add_slivers(node_elem.element, sliver)

        # remove all nodes without slivers
        if not append:
            for node_elem in self.get_nodes():
                if not node_elem['slivers']:
                    parent = node_elem.element.getparent()
                    parent.remove(node_elem.element)


    def remove_slivers(self, slivers, network=None, no_dupes=False):
        SFAv1Node.remove_slivers(self.xml, slivers)
 
    def get_slice_attributes(self, network=None):
        attributes = []
        nodes_with_slivers = self.get_nodes_with_slivers()
        for default_attribute in self.get_default_sliver_attributes(network):
            attribute = default_attribute.copy()
            attribute['node_id'] = None
            attributes.append(attribute)
        for node in nodes_with_slivers:
            nodename=node['component_name']
            sliver_attributes = self.get_sliver_attributes(nodename, network)
            for sliver_attribute in sliver_attributes:
                sliver_attribute['node_id'] = nodename
                attributes.append(sliver_attribute)
        return attributes


    def add_sliver_attribute(self, component_id, name, value, network=None):
        nodes = self.get_nodes({'component_id': '*%s*' % component_id})
        if nodes is not None and isinstance(nodes, list) and len(nodes) > 0:
            node = nodes[0]
            slivers = SFAv1Sliver.get_slivers(node)
            if slivers:
                sliver = slivers[0]
                SFAv1Sliver.add_sliver_attribute(sliver, name, value)
        else:
            # should this be an assert / raise an exception?
            logger.error("WARNING: failed to find component_id %s" % component_id)

    def get_sliver_attributes(self, component_id, network=None):
        nodes = self.get_nodes({'component_id': '*%s*' % component_id})
        attribs = []
        if nodes is not None and isinstance(nodes, list) and len(nodes) > 0:
            node = nodes[0]
            slivers = SFAv1Sliver.get_slivers(node.element)
            if slivers is not None and isinstance(slivers, list) and len(slivers) > 0:
                sliver = slivers[0]
                attribs = SFAv1Sliver.get_sliver_attributes(sliver.element)
        return attribs

    def remove_sliver_attribute(self, component_id, name, value, network=None):
        attribs = self.get_sliver_attributes(component_id)
        for attrib in attribs:
            if attrib['name'] == name and attrib['value'] == value:
                #attrib.element.delete()
                parent = attrib.element.getparent()
                parent.remove(attrib.element)

    def add_default_sliver_attribute(self, name, value, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults")
        if not defaults:
            if network:
                network_tag = self.xml.xpath("//network[@name='%s']" % network)
            else:
                network_tag = self.xml.xpath("//network")    
            if isinstance(network_tag, list):
                network_tag = network_tag[0]
            defaults = network_tag.add_element('sliver_defaults')
        elif isinstance(defaults, list):
            defaults = defaults[0]
        SFAv1Sliver.add_sliver_attribute(defaults, name, value)

    def get_default_sliver_attributes(self, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults")
        if not defaults: return []
        return SFAv1Sliver.get_sliver_attributes(defaults[0])
    
    def remove_default_sliver_attribute(self, name, value, network=None):
        attribs = self.get_default_sliver_attributes(network)
        for attrib in attribs:
            if attrib['name'] == name and attrib['value'] == value:
                #attrib.element.delete()
                parent = attrib.element.getparent()
                parent.remove(attrib.element)

    # utility

    def merge(self, in_rspec):
        """
        Merge contents for specified rspec with current rspec
        """

        if not in_rspec:
            return

        from sfa.rspecs.rspec import RSpec
        if isinstance(in_rspec, RSpec):
            rspec = in_rspec
        else:
            rspec = RSpec(in_rspec)
        if rspec.version.type.lower() == 'protogeni':
            from sfa.rspecs.rspec_converter import RSpecConverter
            in_rspec = RSpecConverter.to_sfa_rspec(rspec.toxml())
            rspec = RSpec(in_rspec)

        # just copy over all networks
        current_networks = self.get_networks()
        networks = rspec.version.get_networks()
        for network in networks:
            current_network = network.get('name')
            if current_network and current_network not in current_networks:
                self.xml.append(network.element)
                current_networks.append(current_network)

if __name__ == '__main__':
    import sys
    import pprint
    from sfa.rspecs.rspec import RSpec
    from sfa.rspecs.rspec_elements import *
    print "main ofeliav1"
    if len(sys.argv)!=2:
        r = RSpec('/tmp/resources.rspec')
    else:
        r = RSpec(sys.argv[1], version = 'OFELIA 1')
    #print r.version.get_datapaths()
    resources = r.version.get_resources()
    pprint.pprint(resources)

    #r.load_rspec_elements(SFAv1.elements)
    #print r.get(RSpecElements.NODE)
