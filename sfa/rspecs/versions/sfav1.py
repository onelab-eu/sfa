from copy import deepcopy
from lxml import etree
from sfa.util.xrn import hrn_to_urn, urn_to_hrn
from sfa.util.plxrn import PlXrn
from sfa.rspecs.rspec_version import BaseVersion
from sfa.rspecs.rspec_elements import RSpecElement, RSpecElements
from sfa.rspecs.elements.versions.pgv2Link import PGv2Link
from sfa.rspecs.elements.versions.sfav1Node import SFAv1Node

class SFAv1(BaseVersion):
    enabled = True
    type = 'SFA'
    content_type = '*'
    version = '1'
    schema = None
    namespace = None
    extensions = {}
    namespaces = None
    elements = [] 
    template = '<RSpec type="%s"></RSpec>' % type

    def get_network_elements(self):
        return self.xml.xpath('//network')

    def get_networks(self):
        return self.xml.xpath('//network[@name]/@name')

    def get_nodes(self, network=None):
        return SFAv1Node.get_nodes(self.xml)

    def get_nodes_with_slivers(self, network = None):
        return SFAv1Node.get_nodes_with_slivers(self.xml)

    def attributes_list(self, elem):
        # convert a list of attribute tags into list of tuples
        # (tagnme, text_value)
        opts = []
        if elem is not None:
            for e in elem:
                opts.append((e.tag, str(e.text).strip()))
        return opts

    def get_default_sliver_attributes(self, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults")
        if isinstance(defaults, list) and defaults:
            defaults = defaults[0]
        return self.attributes_list(defaults)

    def get_sliver_attributes(self, hostname, network=None):
        attributes = []
        node = self.get_node_element(hostname, network)
        #sliver = node.find("sliver")
        slivers = node.xpath('./sliver')
        if isinstance(slivers, list) and slivers:
            attributes = self.attributes_list(slivers[0])
        return attributes

    def get_slice_attributes(self, network=None):
        slice_attributes = []
        nodes_with_slivers = self.get_nodes_with_slivers(network)
        for default_attribute in self.get_default_sliver_attributes(network):
            attribute = {'name': str(default_attribute[0]), 'value': str(default_attribute[1]), 'node_id': None}
            slice_attributes.append(attribute)
        for node in nodes_with_slivers:
            sliver_attributes = self.get_sliver_attributes(node, network)
            for sliver_attribute in sliver_attributes:
                attribute = {'name': str(sliver_attribute[0]), 'value': str(sliver_attribute[1]), 'node_id': node}
                slice_attributes.append(attribute)
        return slice_attributes

    def get_links(self, network=None):
        return PGv2Link.get_links(self.xml)

    def get_link_requests(self):
        return PGv2Link.get_link_requests(self.xml) 

    ##################
    # Builder
    ##################

    def add_network(self, network):
        network_tags = self.xml.xpath('//network[@name="%s"]' % network)
        if not network_tags:
            network_tag = etree.SubElement(self.xml.root, 'network', name=network)
        else:
            network_tag = network_tags[0]
        return network_tag

    def add_nodes(self, nodes, network = None, no_dupes=False):
        SFAv1Node.add_nodes(self.xml, nodes)

    def merge_node(self, source_node_tag, network, no_dupes=False):
        if no_dupes and self.get_node_element(node['hostname']):
            # node already exists
            return

        network_tag = self.add_network(network)
        network_tag.append(deepcopy(source_node_tag))

    def add_links(self, links):
        networks = self.get_network_elements()
        if len(networks) > 0:
            xml = networks[0]
        else:
            xml = self.xml    
        PGv2Link.add_links(xml, links)

    def add_link_requests(self, links):
        PGv2Link.add_link_requests(self.xml, links)

    def add_slivers(self, slivers, network=None, sliver_urn=None, no_dupes=False, append=False):
        # add slice name to network tag
        network_tags = self.xml.xpath('//network')
        if network_tags:
            network_tag = network_tags[0]
            network_tag.set('slice', urn_to_hrn(sliver_urn)[0])
        
        all_nodes = self.get_nodes()
        nodes_with_slivers = [sliver['hostname'] for sliver in slivers]
        nodes_without_slivers = set(all_nodes).difference(nodes_with_slivers)
        
        # add slivers
        for sliver in slivers:
            node_elem = self.get_node_element(sliver['hostname'], network)
            if not node_elem: continue
            sliver_elem = etree.SubElement(node_elem, 'sliver')
            if 'tags' in sliver:
                for tag in sliver['tags']:
                    etree.SubElement(sliver_elem, tag['tagname']).text = value=tag['value']
            
        # remove all nodes without slivers
        if not append:
            for node in nodes_without_slivers:
                node_elem = self.get_node_element(node)
                parent = node_elem.getparent()
                parent.remove(node_elem)

    def remove_slivers(self, slivers, network=None, no_dupes=False):
        SFAv1Node.remove_slivers(self.xml, slivers)

    def add_default_sliver_attribute(self, name, value, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults" % network)
        if not defaults :
            network_tag = self.xml.xpath("//network[@name='%s']" % network)
            if isinstance(network_tag, list):
                network_tag = network_tag[0]
            defaults = self.xml.add_element('sliver_defaults', attrs={}, parent=network_tag)
        elif isinstance(defaults, list):
            defaults = defaults[0]
        self.xml.add_attribute(defaults, name, value)

    def add_sliver_attribute(self, hostname, name, value, network=None):
        node = self.get_node_element(hostname, network)
        sliver = node.find("sliver")
        self.xml.add_attribute(sliver, name, value)

    def remove_default_sliver_attribute(self, name, value, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults" % network)
        self.xml.remove_attribute(defaults, name, value)

    def remove_sliver_attribute(self, hostname, name, value, network=None):
        node = self.get_node_element(hostname, network)
        sliver = node.find("sliver")
        self.xml.remove_attribute(sliver, name, value)

    def merge(self, in_rspec):
        """
        Merge contents for specified rspec with current rspec
        """

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
        networks = rspec.version.get_network_elements()
        for network in networks:
            current_network = network.get('name')
            if current_network and current_network not in current_networks:
                self.xml.root.append(network)
                current_networks.append(current_network)

if __name__ == '__main__':
    from sfa.rspecs.rspec import RSpec
    from sfa.rspecs.rspec_elements import *
    r = RSpec('/tmp/resources.rspec')
    r.load_rspec_elements(SFAv1.elements)
    print r.get(RSpecElements.NODE)
