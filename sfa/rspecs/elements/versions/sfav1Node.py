
from sfa.util.xml import XpathFilter
from sfa.util.plxrn import PlXrn, xrn_to_hostname
from sfa.util.xrn import Xrn
from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.node import Node
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.disk_image import DiskImage
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.elements.bwlimit import BWlimit
from sfa.rspecs.elements.pltag import PLTag
from sfa.rspecs.elements.versions.sfav1Sliver import SFAv1Sliver
from sfa.rspecs.elements.versions.sfav1PLTag import SFAv1PLTag
from sfa.rspecs.elements.versions.pgv2Services import PGv2Services

class SFAv1Node:

    @staticmethod
    def add_nodes(xml, nodes):
        network_elems = Element.get_elements(xml, '//network', fields=['name'])
        if len(network_elems) > 0:
            network_elem = network_elems[0]
        elif len(nodes) > 0 and nodes[0].get('component_manager_id'):
            network_urn = nodes[0]['component_manager_id']    
            network_elems = Element.add_elements(xml, 'network', {'name': Xrn(network_urn).get_hrn()})
            network_elem = network_elems[0]

        node_elems = []       
        for node in nodes:
            node_fields = ['component_manager_id', 'component_id', 'boot_state']
            elems = Element.add_elements(network_elem, 'node', node, node_fields)
            node_elem = elems[0]  
            node_elems.append(node_elem)

            # determine network hrn
            network_hrn = None 
            if 'component_manager_id' in node and node['component_manager_id']:
                network_hrn = Xrn(node['component_manager_id']).get_hrn()

            # set component_name attribute and  hostname element
            if 'component_id' in node and node['component_id']:
                component_name = xrn_to_hostname(node['component_id'])
                node_elem.set('component_name', component_name)
                hostname_tag = node_elem.add_element('hostname')
                hostname_tag.set_text(component_name)

            # set site id
            if 'authority_id' in node and node['authority_id']:
                node_elem.set('site_id', node['authority_id'])

            location_elems = Element.add_elements(node_elem, 'location',
                                                  node.get('location', []), Location.fields)
            interface_elems = Element.add_elements(node_elem, 'interface', 
                                                   node.get('interfaces', []), Interface.fields)
            
            #if 'bw_unallocated' in node and node['bw_unallocated']:
            #    bw_unallocated = etree.SubElement(node_elem, 'bw_unallocated', units='kbps').text = str(int(node['bw_unallocated'])/1000)

            PGv2Services.add_services(node_elem, node.get('services', []))
            SFAv1PLTag.add_pl_tags(node_elem, node.get('tags', [])) 
            SFAv1Sliver.add_slivers(node_elem, node.get('slivers', []))

    @staticmethod 
    def add_slivers(xml, slivers):
        component_ids = []
        for sliver in slivers:
            filter = {}
            if isinstance(sliver, str):
                filter['component_id'] = '*%s*' % sliver
                sliver = {}
            elif 'component_id' in sliver and sliver['component_id']:
                filter['component_id'] = '*%s*' % sliver['component_id']
            if not fliter:
                continue 
            nodes = SFAv1Node.get_nodes(xml, filter)
            if not nodes:
                continue
            node = nodes[0]
            SFAv1Sliver.add_slivers(node, sliver)

    @staticmethod
    def remove_slivers(xml, hostnames):
        for hostname in hostnames:
            nodes = SFAv1Node.get_nodes(xml, {'component_id': '*%s*' % hostname})
            for node in nodes:
                slivers = SFAv1Slivers.get_slivers(node.element)
                for sliver in slivers:
                    node.element.remove(sliver.element)
        
    @staticmethod
    def get_nodes(xml, filter={}):
        xpath = '//node%s | //default:node%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
        node_elems = xml.xpath(xpath)
        return SFAv1Node.get_node_objs(node_elems)

    @staticmethod
    def get_nodes_with_slivers(xml):
        xpath = '//node/sliver | //default:node/default:sliver' 
        node_elems = xml.xpath(xpath)
        return SFAv1Node.get_node_objs(node_elems)


    @staticmethod
    def get_node_objs(node_elems):
        nodes = []    
        for node_elem in node_elems:
            node = Node(node_elem.attrib, node_elem)
            if 'site_id' in node_elem.attrib:
                node['authority_id'] = node_elem.attrib['site_id']
            location_objs = Element.get_elements(node_elem, './default:location | ./location', Location)
            if len(location_objs) > 0:
                node['location'] = location_objs[0]
            bwlimit_objs = Element.get_elements(node_elem, './default:bw_limit | ./bw_limit', BWlimit)
            if len(bwlimit_objs) > 0:
                node['bwlimit'] = bwlimit_objs[0]
            node['interfaces'] = Element.get_elements(node_elem, './default:interface | ./interface', Interface)
            node['services'] = PGv2Services.get_services(node_elem) 
            node['slivers'] = SFAv1Sliver.get_slivers(node_elem)
#thierry    node['tags'] =  SFAv1PLTag.get_pl_tags(node_elem, ignore=Node.fields.keys())
            node['tags'] =  SFAv1PLTag.get_pl_tags(node_elem, ignore=Node.fields)
            nodes.append(node)
        return nodes            
            
