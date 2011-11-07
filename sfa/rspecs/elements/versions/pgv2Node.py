
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

class PGv2Node:
    elements = {
        'node': RSpecElement(RSpecElements.NODE, '//default:node | //node'),
        'sliver': RSpecElement(RSpecElements.SLIVER, './default:sliver_type | ./sliver_type'),
        'interface': RSpecElement(RSpecElements.INTERFACE, './default:interface | ./interface'),
        'location': RSpecElement(RSpecElements.LOCATION, './default:location | ./location'),
        'hardware_type': RSpecElement(RSpecElements.HARDWARE_TYPE, './default:hardware_type | ./hardware_type'),
        'available': RSpecElement(RSpecElements.AVAILABLE, './default:available | ./available'),
    } 
    
    @staticmethod
    def add_nodes(xml, nodes):
        node_elems = []
        for node in nodes:
            node_elem = etree.SubElement(xml, 'node')
            node_elems.append(node_elem)
            if node.get('component_manager_id'):
                node_elem.set('component_manager_id', node['component_manager_id'])
            if node.get('component_id'):
                node_elem.set('component_id', node['component_id'])
                component_name = Xrn(node['component_id']).get_leaf()
                node_elem.set('component_nama', component_name)
            if node.get('client_id'):
                node_elem.set('client_id', node['client_id'])
            if node.get('exclusive'):
                node_elem.set('exclusive', node['exclusive'])
            hardware_types = node.get('hardware_type', [])
            for hardware_type in hardware_types:
                hw_type_elem = etree.SubElement(node_elem, 'hardware_type')
                if hardware_type.get('name'):
                    hw_type_elem.set('name', hardware_type['name'])
            if node.get('available') and node['available'].get('now'):
                available_elem = etree.SubElement(node_elem, 'available', \
                  now=node['available']['now'])
            slivers = node.get('slivers', [])
            for sliver in slivers:
                sliver_elem = etree.SubElement(node_elem, 'sliver_type')
                if sliver.get('name'):
                    sliver_elem.set('name', sliver['name'])
                if sliver.get('client_id'):
                    sliver_elem.set('client_id', sliver['client_id'])      
                pl_initscripts = node.get('pl_initscripts', {})
                for pl_initscript in pl_initscripts.values():
                    etree.SubElement(sliver_elem, '{%s}initscript' % xml.namespaces['planetlab'], \
                      name=pl_initscript['name'])
            location = node.get('location')
            #only add locaiton if long and lat are not null
            if location.get('longitute') and location.get('latitude'):
                location_elem = etree.SubElement(node_elem, country=location['country'],
                  latitude=location['latitude'], longitude=location['longiutde'])
        return node_elems

    @staticmethod
    def get_nodes(xml):
        nodes = []
        node_elems = xml.xpath(PGv2Node.elements['node'].path)
        for node_elem in node_elems:
            node = Node(node_elem.attrib, node_elem)
            nodes.append(node) 
            if 'component_id' in node_elem.attrib:
                node['authority_id'] = Xrn(node_elem.attrib['component_id']).get_authority_urn()

            # set hardware type
            node['hardware_types'] = []
            hardware_type_elems = node_elem.xpath(PGv2Node.elements['hardware_type'].path, xml.namespaces)
            for hardware_type_elem in hardware_type_elems:
                node['hardware_types'].append(HardwareType(hardware_type_elem.attrib, hardware_type_elem))
            
            # set location
            location_elems = node_elem.xpath(PGv2Node.elements['location'].path, xml.namespaces)
            if len(location_elems) > 0:
                node['location'] = Location(location_elems[0].attrib, location_elems[0])
            
            # set interfaces
            interface_elems = node_elem.xpath(PGv2Node.elements['interface'].path, xml.namespaces)
            node['interfaces'] = []
            for interface_elem in interface_elems:
                node['interfaces'].append(Interface(interface_elem.attrib, interface_elem))

            # set available
            available = node_elem.xpath(PGv2Node.elements['available'].path, xml.namespaces)
            if len(available) > 0:
                node['available'] = available[0].attrib 

            # set the slivers
            sliver_elems = node_elem.xpath(PGv2Node.elements['sliver'].path, xml.namespaces)
            node['slivers'] = []
            for sliver_elem in sliver_elems:
                node['slivers'].append(Sliver(sliver_elem.attrib, sliver_elem))            

        return nodes


    @staticmethod
    def add_slivers(xml, slivers):
        pass
   
    @staticmethod
    def get_nodes_with_slivers(xml):
        nodes = PGv2Node.get_nodes(xml)
        nodes_with_slivers = [node for node in nodes if node['slivers']]
        return nodes_with_slivers 

if __name__ == '__main__':
    from sfa.rspecs.rspec import RSpec
    import pdb
    r = RSpec('/tmp/emulab.rspec')
    r2 = RSpec(version = 'ProtoGENI')
    nodes = PGv2Node.get_nodes(r.xml)
    PGv2Node.add_nodes(r2.xml.root, nodes)
    #pdb.set_trace()
        
                                    
