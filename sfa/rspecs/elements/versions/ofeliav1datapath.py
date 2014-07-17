from sfa.util.sfalogging import logger
from sfa.util.xml import XpathFilter
from sfa.util.xrn import Xrn, get_leaf

from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.datapath import Datapath
from sfa.rspecs.elements.node import NodeElement
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
from sfa.rspecs.elements.versions.ofeliav1Port import Ofeliav1Port


class Ofeliav1Datapath:

    @staticmethod
    def get_datapaths(xml, filter=None):
        if filter is None: filter={}
        #xpath = '//datapath%s | //default:datapath%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
        xpath = '//datapath%s | //openflow:datapath%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
        datapath_elems = xml.xpath(xpath)
        return Ofeliav1Datapath.get_datapath_objs(datapath_elems)

    @staticmethod
    def get_datapath_objs(datapath_elems):
        datapaths = []    
        for datapath_elem in datapath_elems:
            datapath = Datapath(datapath_elem.attrib, datapath_elem)
            # get ports
            datapath['ports'] =  Ofeliav1Port.get_ports(datapath_elem)
            datapaths.append(datapath)
        return datapaths            

#    @staticmethod
#    def add_nodes(xml, nodes, rspec_content_type=None):
#        network_elems = xml.xpath('//network')
#        if len(network_elems) > 0:
#            network_elem = network_elems[0]
#        elif len(nodes) > 0 and nodes[0].get('component_manager_id'):
#            network_urn = nodes[0]['component_manager_id']
#            network_elem = xml.add_element('network', name = Xrn(network_urn).get_hrn())
#        else:
#            network_elem = xml
#
#        node_elems = []       
#        for node in nodes:
#            node_fields = ['component_manager_id', 'component_id', 'boot_state']
#            node_elem = network_elem.add_instance('node', node, node_fields)
#            node_elems.append(node_elem)
#
#            # determine network hrn
#            network_hrn = None 
#            if 'component_manager_id' in node and node['component_manager_id']:
#                network_hrn = Xrn(node['component_manager_id']).get_hrn()
#
#            # set component_name attribute and  hostname element
#            if 'component_id' in node and node['component_id']:
#                component_name = Xrn.unescape(get_leaf(Xrn(node['component_id']).get_hrn()))
#                node_elem.set('component_name', component_name)
#                hostname_elem = node_elem.add_element('hostname')
#                hostname_elem.set_text(component_name)
#
#            # set site id
#            if 'authority_id' in node and node['authority_id']:
#                node_elem.set('site_id', node['authority_id'])
#
#            # add locaiton
#            location = node.get('location')
#            if location:
#                node_elem.add_instance('location', location, Location.fields)
#
#            # add exclusive tag to distinguish between Reservable and Shared nodes
#            exclusive_elem = node_elem.add_element('exclusive')
#            if node.get('exclusive') and node.get('exclusive') == 'true':
#                exclusive_elem.set_text('TRUE')
#                # add granularity of the reservation system
#                granularity = node.get('granularity')
#                if granularity:
#                    node_elem.add_instance('granularity', granularity, granularity.fields)
#            else:
#                exclusive_elem.set_text('FALSE')
#
#
#            if isinstance(node.get('interfaces'), list):
#                for interface in node.get('interfaces', []):
#                    node_elem.add_instance('interface', interface, ['component_id', 'client_id', 'ipv4']) 
#            
#            #if 'bw_unallocated' in node and node['bw_unallocated']:
#            #    bw_unallocated = etree.SubElement(node_elem, 'bw_unallocated', units='kbps').text = str(int(node['bw_unallocated'])/1000)
#
#            PGv2Services.add_services(node_elem, node.get('services', []))
#            tags = node.get('tags', [])
#            if tags:
#                for tag in tags:
#                    # backdoor for FITeagle
#                    # Alexander Willner <alexander.willner@tu-berlin.de>
#                    if tag['tagname']=="fiteagle_settings":
#                        tag_elem = node_elem.add_element(tag['tagname'])
#                        for subtag in tag['value']:
#                            subtag_elem = tag_elem.add_element('setting')
#                            subtag_elem.set('name', str(subtag['tagname']))
#                            subtag_elem.set('description', str(subtag['description']))
#                            subtag_elem.set_text(subtag['value'])
#                    else:
#                        tag_elem = node_elem.add_element(tag['tagname'])
#                        tag_elem.set_text(tag['value'])
#            SFAv1Sliver.add_slivers(node_elem, node.get('slivers', []))
#
#            # add sliver tag in Request Rspec
#            if rspec_content_type == "request":
#                node_elem.add_instance('sliver', '', []) 
#
#    @staticmethod 
#    def add_slivers(xml, slivers):
#        component_ids = []
#        for sliver in slivers:
#            filter = {}
#            if isinstance(sliver, str):
#                filter['component_id'] = '*%s*' % sliver
#                sliver = {}
#            elif 'component_id' in sliver and sliver['component_id']:
#                filter['component_id'] = '*%s*' % sliver['component_id']
#            if not filter:
#                continue 
#            nodes = SFAv1Node.get_nodes(xml, filter)
#            if not nodes:
#                continue
#            node = nodes[0]
#            SFAv1Sliver.add_slivers(node, sliver)
#
#    @staticmethod
#    def remove_slivers(xml, hostnames):
#        for hostname in hostnames:
#            nodes = SFAv1Node.get_nodes(xml, {'component_id': '*%s*' % hostname})
#            for node in nodes:
#                slivers = SFAv1Sliver.get_slivers(node.element)
#                for sliver in slivers:
#                    node.element.remove(sliver.element)
#        
#    @staticmethod
#    def get_nodes(xml, filter=None):
#        if filter is None: filter={}
#        xpath = '//node%s | //default:node%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
#        node_elems = xml.xpath(xpath)
#        return SFAv1Node.get_node_objs(node_elems)
#
#    @staticmethod
#    def get_nodes_with_slivers(xml):
#        xpath = '//node[count(sliver)>0] | //default:node[count(default:sliver)>0]' 
#        node_elems = xml.xpath(xpath)
#        return SFAv1Node.get_node_objs(node_elems)
#
