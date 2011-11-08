
from lxml import etree
from sfa.util.plxrn import PlXrn
from sfa.util.xrn import Xrn
from sfa.rspecs.elements.node import Node
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.network import Network 
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.disk_image import DiskImage
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.elements.bwlimit import BWlimit
from sfa.rspecs.elements.pl_tag import PLTag
from sfa.rspecs.rspec_elements import RSpecElement, RSpecElements
from sfa.rspecs.elements.versions.sfav1Network import SFAv1Network
from sfa.rspecs.elements.versions.pgv2Services import PGv2Services

class SFAv1Node:

    elements = {
        'node': RSpecElement(RSpecElements.NODE, '//default:node | //node'),
        'sliver': RSpecElement(RSpecElements.SLIVER, './default:sliver | ./sliver'),
        'interface': RSpecElement(RSpecElements.INTERFACE, './default:interface | ./interface'),
        'location': RSpecElement(RSpecElements.LOCATION, './default:location | ./location'),
        'bw_limit': RSpecElement(RSpecElements.BWLIMIT, './default:bw_limit | ./bw_limit'),
    }
    
    @staticmethod
    def add_nodes(xml, nodes):
        network_elems = SFAv1Network.get_networks(xml)
        if len(network_elems) > 0:
            network_elem = network_elems[0]
        elif len(nodes) > 0 and nodes[0].get('component_manager_id'):
            network_elem = SFAv1Network.add_network(xml.root, {'name': nodes[0]['component_manager_id']})
            

        node_elems = []       
        for node in nodes:
            node_elem = etree.SubElement(network_elem, 'node')
            node_elems.append(node_elem)
            network = None 
            if 'component_manager_id' in node and node['component_manager_id']:
                node_elem.set('component_manager_id', node['component_manager_id'])
                network = Xrn(node['component_manager_id']).get_hrn()
            if 'component_id' in node and node['component_id']:
                node_elem.set('component_id', node['component_id'])
                xrn = Xrn(node['component_id'])
                node_elem.set('component_name', xrn.get_leaf())
                hostname_tag = etree.SubElement(node_elem, 'hostname').text = xrn.get_leaf()
            if 'authority_id' in node and node['authority_id']:
                node_elem.set('site_id', node['authority_id'])
            if 'boot_state' in node and node['boot_state']:
                node_elem.set('boot_state', node['boot_state'])
            if 'location' in node and node['location']:
                location_elem = etree.SubElement(node_elem, 'location')
                for field in Location.fields:
                    if field in node['location'] and node['location'][field]:
                        location_elem.set(field, node['location'][field])
            if 'interfaces' in node and node['interfaces']:
                i = 0
                for interface in node['interfaces']:
                    if 'bwlimit' in interface and interface['bwlimit']:
                        bwlimit = etree.SubElement(node_elem, 'bw_limit', units='kbps').text = str(interface['bwlimit']/1000)
                    comp_id = PlXrn(auth=network, interface='node%s:eth%s' % (interface['node_id'], i)).get_urn()
                    ipaddr = interface['ipv4']
                    interface_elem = etree.SubElement(node_elem, 'interface', component_id=comp_id, ipv4=ipaddr)
                    i+=1
            if 'bw_unallocated' in node and node['bw_unallocated']:
                bw_unallocated = etree.SubElement(node_elem, 'bw_unallocated', units='kbps').text = str(int(node['bw_unallocated'])/1000)

            if node.get('services'):
                PGv2Services.add_services(node_elem, node.get('services'))

            if 'tags' in node:
                for tag in node['tags']:
                   # expose this hard wired list of tags, plus the ones that are marked 'sfa' in their category
                   if tag['name'] in ['fcdistro', 'arch']:
                        tag_element = etree.SubElement(node_elem, tag['name']).text=tag['value']

            if node.get('slivers'):
                for sliver in node['slivers']:
                    sliver_elem = etree.SubElement(node_elem, 'sliver')
                    if sliver.get('sliver_id'): 
                        sliver_id_leaf = Xrn(sliver.get('sliver_id')).get_leaf()
                        sliver_id_parts = sliver_id_leaf.split(':')
                        name = sliver_id_parts[0] 
                        sliver_elem.set('name', name) 

    @staticmethod 
    def add_slivers(xml, slivers):
        pass

    @staticmethod
    def get_nodes(xml):
        nodes = []
        node_elems = xml.xpath(SFAv1Node.elements['node'].path)
        for node_elem in node_elems:
            node = Node(node_elem.attrib, node_elem)
            if 'site_id' in node_elem.attrib:
                node['authority_id'] = node_elem.attrib['site_id']
            if 'authority_id' in node_elem.attrib:
                node['authority_id'] = node_elem.attrib['authority_id']
 
            # set the location
            location_elems = node_elem.xpath(SFAv1Node.elements['location'].path, xml.namespaces)
            if len(location_elems) > 0:
                node['location'] = Location(location_elems[0].attrib, location_elems[0])
            
            # set the bwlimit
            bwlimit_elems = node_elem.xpath(SFAv1Node.elements['bw_limit'].path, xml.namespaces)
            if len(bwlimit_elems) > 0:
                bwlimit = BWlimit(bwlimit_elems[0].attrib, bwlimit_elems[0])
                node['bwlimit'] = bwlimit

            # set the interfaces
            interface_elems = node_elem.xpath(SFAv1Node.elements['interface'].path, xml.namespaces)
            node['interfaces'] = []
            for interface_elem in interface_elems:
                node['interfaces'].append(Interface(interface_elem.attrib, interface_elem))
            
            # set the slivers
            sliver_elems = node_elem.xpath(SFAv1Node.elements['sliver'].path, xml.namespaces)
            node['slivers'] = []
            for sliver_elem in sliver_elems:
                node['slivers'].append(Sliver(sliver_elem.attrib, sliver_elem))
            
            # set tags
            node['tags'] = [] 
            for child in node_elem.iterchildren():
                if child.tag not in SFAv1Node.elements:
                    tag = PLTag({'name': child.tag, 'value': child.text}, child)  
                    node['tags'].append(tag) 
            nodes.append(node)
        return nodes
        
    @staticmethod
    def get_nodes_with_slivers(xml):
        nodes = SFAv1Node.get_nodes(xml)
        nodes_with_slivers = [node for node in nodes if node['slivers']]
        return nodes_with_slivers
    
             
