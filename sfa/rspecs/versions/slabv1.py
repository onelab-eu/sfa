from copy import deepcopy
from StringIO import StringIO
from sfa.util.xrn import Xrn, urn_to_sliver_id
from sfa.util.plxrn import hostname_to_urn, xrn_to_hostname 
from sfa.rspecs.baseversion import BaseVersion

from sfa.rspecs.elements.versions.slabv1Node import Slabv1Node
from sfa.rspecs.elements.versions.slabv1Sliver import Slabv1Sliver
 
class Slabv1(BaseVersion):
    #enabled = True
    type = 'Slab'
    content_type = 'ad'
    version = '1'
    #template = '<RSpec type="%s"></RSpec>' % type

    schema = 'http://senslab.info/resources/rspec/1/ad.xsd'
    namespace = 'http://www.geni.net/resources/rspec/3'
    extensions = {
        'flack': "http://www.protogeni.net/resources/rspec/ext/flack/1",
        'planetlab': "http://www.planet-lab.org/resources/sfa/ext/planetlab/1",
    }
    namespaces = dict(extensions.items() + [('default', namespace)])
    elements = []
    
    # Network 
    def get_networks(self):
        network_elems = self.xml.xpath('//network')
        networks = [network_elem.get_instance(fields=['name', 'slice']) for \
                    network_elem in network_elems]
        return networks    


    def add_network(self, network):
        network_tags = self.xml.xpath('//network[@name="%s"]' % network)
        if not network_tags:
            network_tag = self.xml.add_element('network', name=network)
        else:
            network_tag = network_tags[0]
        return network_tag

   
    # Nodes

    def get_nodes(self, filter=None):
        return Slabv1Node.get_nodes(self.xml, filter)

    def get_nodes_with_slivers(self):
        return Slabv1Node.get_nodes_with_slivers(self.xml)

    def add_nodes(self, nodes, check_for_dupes=False):
        return Slabv1Node.add_nodes(self.xml, nodes)
    
    def merge_node(self, source_node_tag, network, no_dupes = False):
        if no_dupes and self.get_node_element(node['hostname']):
            # node already exists
            return
        network_tag = self.add_network(network)
        network_tag.append(deepcopy(source_node_tag))

    # Slivers
    
    def get_sliver_attributes(self, hostname, network=None):
        nodes = self.get_nodes({'component_id': '*%s*' %hostname})
        attribs = []
        if nodes is not None and isinstance(nodes, list) and len(nodes) > 0:
            node = nodes[0]
            sliver = node.xpath('./default:sliver_type', namespaces=self.namespaces)
            if sliver is not None and isinstance(sliver, list) and len(sliver) > 0:
                sliver = sliver[0]
                #attribs = self.attributes_list(sliver)
        return attribs

    def get_slice_attributes(self, network=None):
        slice_attributes = []
        nodes_with_slivers = self.get_nodes_with_slivers()
        # TODO: default sliver attributes in the PG rspec?
        default_ns_prefix = self.namespaces['default']
        for node in nodes_with_slivers:
            sliver_attributes = self.get_sliver_attributes(node, network)
            for sliver_attribute in sliver_attributes:
                name=str(sliver_attribute[0])
                text =str(sliver_attribute[1])
                attribs = sliver_attribute[2]
                # we currently only suppor the <initscript> and <flack> attributes
                if  'info' in name:
                    attribute = {'name': 'flack_info', 'value': str(attribs), 'node_id': node}
                    slice_attributes.append(attribute)
                elif 'initscript' in name:
                    if attribs is not None and 'name' in attribs:
                        value = attribs['name']
                    else:
                        value = text
                    attribute = {'name': 'initscript', 'value': value, 'node_id': node}
                    slice_attributes.append(attribute)

        return slice_attributes

    def attributes_list(self, elem):
        opts = []
        if elem is not None:
            for e in elem:
                opts.append((e.tag, str(e.text).strip(), e.attrib))
        return opts

    def get_default_sliver_attributes(self, network=None):
        return []

    def add_default_sliver_attribute(self, name, value, network=None):
        pass

    def add_slivers(self, hostnames, attributes=[], sliver_urn=None, append=False):
        # all nodes hould already be present in the rspec. Remove all
        # nodes that done have slivers
        for hostname in hostnames:
            node_elems = self.get_nodes({'component_id': '*%s*' % hostname})
            if not node_elems:
                continue
            node_elem = node_elems[0]
            
            # determine sliver types for this node
            valid_sliver_types = ['slab-node', 'emulab-openvz', 'raw-pc', 'plab-vserver', 'plab-vnode']
            #valid_sliver_types = ['emulab-openvz', 'raw-pc', 'plab-vserver', 'plab-vnode']
            requested_sliver_type = None
            for sliver_type in node_elem.get('slivers', []):
                if sliver_type.get('type') in valid_sliver_types:
                    requested_sliver_type = sliver_type['type']
            
            if not requested_sliver_type:
                continue
            sliver = {'type': requested_sliver_type,
                     'pl_tags': attributes}

            # remove available element
            for available_elem in node_elem.xpath('./default:available | ./available'):
                node_elem.remove(available_elem)
            
            # remove interface elements
            for interface_elem in node_elem.xpath('./default:interface | ./interface'):
                node_elem.remove(interface_elem)
        
            # remove existing sliver_type elements
            for sliver_type in node_elem.get('slivers', []):
                node_elem.element.remove(sliver_type.element)

            # set the client id
            node_elem.element.set('client_id', hostname)
            if sliver_urn:
                pass
                # TODO
                # set the sliver id
                #slice_id = sliver_info.get('slice_id', -1)
                #node_id = sliver_info.get('node_id', -1)
                #sliver_id = urn_to_sliver_id(sliver_urn, slice_id, node_id)
                #node_elem.set('sliver_id', sliver_id)

            # add the sliver type elemnt    
            Slabv1SliverType.add_slivers(node_elem.element, sliver)         

        # remove all nodes without slivers
        if not append:
            for node_elem in self.get_nodes():
                if not node_elem['client_id']:
                    parent = node_elem.element.getparent()
                    parent.remove(node_elem.element)

    def remove_slivers(self, slivers, network=None, no_dupes=False):
        Slabv1Node.remove_slivers(self.xml, slivers) 



    # Utility

    def merge(self, in_rspec):
        """
        Merge contents for specified rspec with current rspec
        """
        from sfa.rspecs.rspec import RSpec
        # just copy over all the child elements under the root element
        if isinstance(in_rspec, basestring):
            in_rspec = RSpec(in_rspec)

        nodes = in_rspec.version.get_nodes()
        # protogeni rspecs need to advertise the availabel sliver types
        for node in nodes:
            if not node.has_key('sliver') or not node['sliver']:
                node['sliver'] = {'name': 'slab-node'}
            
        self.add_nodes(nodes)
        #self.add_links(in_rspec.version.get_links())
        
        #
        #rspec = RSpec(in_rspec)
        #for child in rspec.xml.iterchildren():
        #    self.xml.root.append(child)
        
        

    def cleanup(self):
        # remove unncecessary elements, attributes
        if self.type in ['request', 'manifest']:
            # remove 'available' element from remaining node elements
            self.xml.remove_element('//default:available | //available')
            
            
class Slabv1Ad(Slabv1):
    enabled = True
    content_type = 'ad'
    schema = 'http://senslab.info/resources/rspec/1/ad.xsd'
    #http://www.geni.net/resources/rspec/3/ad.xsd'
    template = '<rspec type="advertisement" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://senslab.info/resources/rspec/1" xmlns:flack="http://senslab.info/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xsi:schemaLocation="http://senslab.info/resources/rspec/1 http://senslab.info/resources/rspec/1/ad.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'

class Slabv1Request(Slabv1):
    enabled = True
    content_type = 'request'
    schema = 'http://senslab.info/resources/rspec/1/request.xsd'
    #http://www.geni.net/resources/rspec/3/request.xsd
    template = '<rspec type="advertisement" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://senslab.info/resources/rspec/1" xmlns:flack="http://senslab.info/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xsi:schemaLocation="http://senslab.info/resources/rspec/1 http://senslab.info/resources/rspec/1/ad.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'

class Slabv1Manifest(Slabv1):
    enabled = True
    content_type = 'manifest'
    schema = 'http://senslab.info/resources/rspec/1/manifest.xsd'
    #http://www.geni.net/resources/rspec/3/manifest.xsd
    template = '<rspec type="advertisement" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://senslab.info/resources/rspec/1" xmlns:flack="http://senslab.info/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xsi:schemaLocation="http://senslab.info/resources/rspec/1 http://senslab.info/resources/rspec/1/ad.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'
#class Slabv1Ad(Slabv1):
    #enabled = True
    #content_type = 'ad'
    #schema = 'http://senslab.info/resources/rspec/1/ad.xsd'
    ##http://www.geni.net/resources/rspec/3/ad.xsd'
    #template = '<rspec type="advertisement" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.geni.net/resources/rspec/3" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/ad.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'

#class Slabv1Request(Slabv1):
    #enabled = True
    #content_type = 'request'
    #schema = 'http://senslab.info/resources/rspec/1/request.xsd'
    ##http://www.geni.net/resources/rspec/3/request.xsd
    #template = '<rspec type="request" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.geni.net/resources/rspec/3" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/request.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'

#class Slabv1Manifest(Slabv1):
    #enabled = True
    #content_type = 'manifest'
    #schema = 'http://senslab.info/resources/rspec/1/manifest.xsd'
    ##http://www.geni.net/resources/rspec/3/manifest.xsd
    #template = '<rspec type="manifest" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.geni.net/resources/rspec/3" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/manifest.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'

     


if __name__ == '__main__':
    from sfa.rspecs.rspec import RSpec
    from sfa.rspecs.rspec_elements import *
    r = RSpec('/tmp/slab.rspec')
    r.load_rspec_elements(Slabv1.elements)
    r.namespaces = Slabv1.namespaces
    print r.get(RSpecElements.NODE)
