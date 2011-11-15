from lxml import etree
from copy import deepcopy
from StringIO import StringIO
from sfa.util.xrn import urn_to_sliver_id
from sfa.util.plxrn import hostname_to_urn, xrn_to_hostname 
from sfa.rspecs.baseversion import BaseVersion
from sfa.rspecs.rspec_elements import RSpecElement, RSpecElements
from sfa.rspecs.elements.versions.pgv2Link import PGv2Link
 
class PGv2(BaseVersion):
    type = 'ProtoGENI'
    content_type = 'ad'
    version = '2'
    schema = 'http://www.protogeni.net/resources/rspec/2/ad.xsd'
    namespace = 'http://www.protogeni.net/resources/rspec/2'
    extensions = {
        'flack': "http://www.protogeni.net/resources/rspec/ext/flack/1",
        'planetlab': "http://www.planet-lab.org/resources/sfa/ext/planetlab/1",
    }
    namespaces = dict(extensions.items() + [('default', namespace)])
    elements = []

    def get_network(self):
        network = None
        nodes = self.xml.xpath('//default:node[@component_manager_id][1]', namespaces=self.namespaces)
        if nodes:
            network  = nodes[0].get('component_manager_id')
        return network

    def get_networks(self):
        networks = self.xml.xpath('//default:node[@component_manager_id]/@component_manager_id', namespaces=self.namespaces)
        return set(networks)

    def get_node_element(self, hostname, network=None):
        nodes = self.xml.xpath('//default:node[@component_id[contains(., "%s")]] | node[@component_id[contains(., "%s")]]' % (hostname, hostname), namespaces=self.namespaces)
        if isinstance(nodes,list) and nodes:
            return nodes[0]
        else:
            return None

    def get_node_elements(self, network=None):
        nodes = self.xml.xpath('//default:node | //node', namespaces=self.namespaces)
        return nodes


    def get_nodes(self, network=None):
        xpath = '//default:node[@component_name]/@component_id | //node[@component_name]/@component_id'
        nodes = self.xml.xpath(xpath, namespaces=self.namespaces)
        nodes = [xrn_to_hostname(node) for node in nodes]
        return nodes

    def get_nodes_with_slivers(self, network=None):
        if network:
            nodes = self.xml.xpath('//default:node[@component_manager_id="%s"][sliver_type]/@component_id' % network, namespaces=self.namespaces)
        else:
            nodes = self.xml.xpath('//default:node[default:sliver_type]/@component_id', namespaces=self.namespaces)
        nodes = [xrn_to_hostname(node) for node in nodes]
        return nodes

    def get_nodes_without_slivers(self, network=None):
        return []

    def get_sliver_attributes(self, hostname, network=None):
        node = self.get_node_element(hostname, network)
        sliver = node.xpath('./default:sliver_type', namespaces=self.namespaces)
        if sliver is not None and isinstance(sliver, list):
            sliver = sliver[0]
        return self.attributes_list(sliver)

    def get_slice_attributes(self, network=None):
        slice_attributes = []
        nodes_with_slivers = self.get_nodes_with_slivers(network)
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

    def get_links(self, network=None):
        return PGv2Link.get_links(self.xml)

    def get_link_requests(self):
        return PGv2Link.get_link_requests(self.xml)  

    def add_links(self, links):
        PGv2Link.add_links(self.xml.root, links)

    def add_link_requests(self, link_tuples, append=False):
        PGv2Link.add_link_requests(self.xml.root, link_tuples, append)

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

    def add_nodes(self, nodes, check_for_dupes=False):
        if not isinstance(nodes, list):
            nodes = [nodes]
        for node in nodes:
            urn = ""
            if check_for_dupes and \
              self.xml.xpath('//default:node[@component_uuid="%s"]' % urn, namespaces=self.namespaces):
                # node already exists
                continue

            node_tag = etree.SubElement(self.xml.root, 'node', exclusive='false')
            if 'network_urn' in node:
                node_tag.set('component_manager_id', node['network_urn'])
            if 'urn' in node:
                node_tag.set('component_id', node['urn'])
            if 'hostname' in node:
                node_tag.set('component_name', node['hostname'])
            # TODO: should replace plab-pc with pc model
            node_type_tag = etree.SubElement(node_tag, 'hardware_type', name='plab-pc')
            node_type_tag = etree.SubElement(node_tag, 'hardware_type', name='pc')
            available_tag = etree.SubElement(node_tag, 'available', now='true')
            sliver_type_tag = etree.SubElement(node_tag, 'sliver_type', name='plab-vserver')

            pl_initscripts = node.get('pl_initscripts', {})
            for pl_initscript in pl_initscripts.values():
                etree.SubElement(sliver_type_tag, '{%s}initscript' % self.namespaces['planetlab'], name=pl_initscript['name'])

            # protogeni uses the <sliver_type> tag to identify the types of
            # vms available at the node.
            # only add location tag if longitude and latitude are not null
            if 'site' in node:
                longitude = node['site'].get('longitude', None)
                latitude = node['site'].get('latitude', None)
                if longitude and latitude:
                    location_tag = etree.SubElement(node_tag, 'location', country="us", \
                                                    longitude=str(longitude), latitude=str(latitude))

    def merge_node(self, source_node_tag):
        # this is untested
        self.xml.root.append(deepcopy(source_node_tag))

    def add_slivers(self, slivers, sliver_urn=None, no_dupes=False, append=False):

        # all nodes hould already be present in the rspec. Remove all
        # nodes that done have slivers
        slivers_dict = {}
        for sliver in slivers:
            if isinstance(sliver, basestring):
                slivers_dict[sliver] = {'hostname': sliver}
            elif isinstance(sliver, dict):
                slivers_dict[sliver['hostname']] = sliver        

        nodes = self.get_node_elements()
        for node in nodes:
            urn = node.get('component_id')
            hostname = xrn_to_hostname(urn)
            if hostname not in slivers_dict and not append:
                parent = node.getparent()
                parent.remove(node)
            else:
                sliver_info = slivers_dict[hostname]
                sliver_type_elements = node.xpath('./default:sliver_type', namespaces=self.namespaces)
                available_sliver_types = [element.attrib['name'] for element in sliver_type_elements]
                valid_sliver_types = ['emulab-openvz', 'raw-pc', 'plab-vserver', 'plab-vnode']
                requested_sliver_type = None
                for valid_sliver_type in valid_sliver_types:
                    if valid_sliver_type in available_sliver_types:
                        requested_sliver_type = valid_sliver_type
                if requested_sliver_type:
                    # remove existing sliver_type tags,it needs to be recreated
                    sliver_elem = node.xpath('./default:sliver_type | ./sliver_type', namespaces=self.namespaces)
                    if sliver_elem and isinstance(sliver_elem, list):
                        sliver_elem = sliver_elem[0]
                        node.remove(sliver_elem)
                    # set the client id
                    node.set('client_id', hostname)
                    if sliver_urn:
                        # set the sliver id
                        slice_id = sliver_info.get('slice_id', -1)
                        node_id = sliver_info.get('node_id', -1)
                        sliver_id = urn_to_sliver_id(sliver_urn, slice_id, node_id)
                        node.set('sliver_id', sliver_id)

                    # add the sliver element
                    sliver_elem = etree.SubElement(node, 'sliver_type', name=requested_sliver_type)
                    for tag in sliver_info.get('tags', []):
                        if tag['tagname'] == 'flack_info':
                            e = etree.SubElement(sliver_elem, '{%s}info' % self.namespaces['flack'], attrib=eval(tag['value']))
                        elif tag['tagname'] == 'initscript':
                            e = etree.SubElement(sliver_elem, '{%s}initscript' % self.namespaces['planetlab'], attrib={'name': tag['value']})                
                else:
                    # node isn't usable. just remove it from the request     
                    parent = node.getparent()
                    parent.remove(node)

    

    def remove_slivers(self, slivers, network=None, no_dupes=False):
        for sliver in slivers:
            node_elem = self.get_node_element(sliver['hostname'])
            sliver_elem = node_elem.xpath('./default:sliver_type', self.namespaces)
            if sliver_elem != None and sliver_elem != []:
                node_elem.remove(sliver_elem[0])

    def add_default_sliver_attribute(self, name, value, network=None):
        pass

    def add_interfaces(self, interfaces, no_dupes=False):
        pass

    def merge(self, in_rspec):
        """
        Merge contents for specified rspec with current rspec
        """
        from sfa.rspecs.rspec import RSpec
        # just copy over all the child elements under the root element
        if isinstance(in_rspec, RSpec):
            in_rspec = in_rspec.toxml()
        tree = etree.parse(StringIO(in_rspec))
        root = tree.getroot()
        for child in root.getchildren():
            self.xml.root.append(child)

    def cleanup(self):
        # remove unncecessary elements, attributes
        if self.type in ['request', 'manifest']:
            # remove 'available' element from remaining node elements
            self.xml.remove_element('//default:available | //available')

class PGv2Ad(PGv2):
    enabled = True
    content_type = 'ad'
    schema = 'http://www.protogeni.net/resources/rspec/2/ad.xsd'
    template = '<rspec type="advertisement" xmlns="http://www.protogeni.net/resources/rspec/2" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.protogeni.net/resources/rspec/2 http://www.protogeni.net/resources/rspec/2/ad.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'

class PGv2Request(PGv2):
    enabled = True
    content_type = 'request'
    schema = 'http://www.protogeni.net/resources/rspec/2/request.xsd'
    template = '<rspec type="request" xmlns="http://www.protogeni.net/resources/rspec/2" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.protogeni.net/resources/rspec/2 http://www.protogeni.net/resources/rspec/2/request.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'

class PGv2Manifest(PGv2):
    enabled = True
    content_type = 'manifest'
    schema = 'http://www.protogeni.net/resources/rspec/2/manifest.xsd'
    template = '<rspec type="manifest" xmlns="http://www.protogeni.net/resources/rspec/2" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.protogeni.net/resources/rspec/2 http://www.protogeni.net/resources/rspec/2/manifest.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd"/>'

     


if __name__ == '__main__':
    from sfa.rspecs.rspec import RSpec
    from sfa.rspecs.rspec_elements import *
    r = RSpec('/tmp/pg.rspec')
    r.load_rspec_elements(PGv2.elements)
    r.namespaces = PGv2.namespaces
    print r.get(RSpecElements.NODE)
