
from sfa.util.xrn import Xrn
from sfa.util.xml import XpathFilter
from sfa.rspecs.elements.node import Node
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.elements.versions.slabv1Sliver import Slabv1Sliver
from sfa.util.sfalogging import logger

class SlabNode(Node):
    #First get the fields already defined in the class Node
    fields = list(Node.fields)
    #Extend it with senslab's specific fields
    fields.extend (['archi', 'radio', 'mobile','position'])
    

class SlabPosition(Element):
    fields = ['posx', 'posy','posz']



class Slabv1Node:
    
    @staticmethod
    def add_connection_information(xml, ldap_username):
        """ Adds login and ssh connection info in the network item in 
        the xml. Does not create the network element, therefore 
        should be used after add_nodes, which creates the network item.
        
        """
        logger.debug(" add_connection_information " )
        #Get network item in the xml
        network_elems = xml.xpath('//network')  
        if len(network_elems) > 0:
            network_elem = network_elems[0]

        slab_network_dict = {}
        slab_network_dict['login'] = ldap_username
        slab_network_dict['vm'] = 'ssh ' + ldap_username + \
                                        '@grenoble.senslab.info'
        network_elem.set('vm', unicode(slab_network_dict['vm']))
        network_elem.set('login', unicode( slab_network_dict['login']))

        
    @staticmethod
    def add_nodes(xml, nodes):
        #Add network item in the xml
        network_elems = xml.xpath('//network')
        if len(network_elems) > 0:
            network_elem = network_elems[0]
        elif len(nodes) > 0 and nodes[0].get('component_manager_id'):
            network_urn = nodes[0]['component_manager_id']
            network_elem = xml.add_element('network', \
                                        name = Xrn(network_urn).get_hrn())
        else:
            network_elem = xml
       
        #logger.debug("slabv1Node \t add_nodes  nodes %s \r\n "%(nodes))
        node_elems = []
        #Then add nodes items to the network item in the xml
        for node in nodes:
            #Attach this node to the network element
            node_fields = ['component_manager_id', 'component_id', 'exclusive',\
                                                    'boot_state', 'mobile']
            node_elem = network_elem.add_instance('node', node, node_fields)
            node_elems.append(node_elem)
            
            #Set the attibutes of this node element
            for attribute in node: 
            # set component name
                if attribute is 'component_id':
                    component_name = node['component_name']
                    node_elem.set('component_name', component_name)
                    
            # set hardware types, extend fields to add Senslab's architecture
            #and radio type
                
                if attribute is 'hardware_types':
                    for hardware_type in node.get('hardware_types', []): 
                        fields = HardwareType.fields
                        fields.extend(['archi','radio'])
                        node_elem.add_instance('hardware_types', node, fields)

            # set location
                if attribute is 'location':
                    node_elem.add_instance('location', node['location'], \
                                                        Location.fields)
             # add granularity of the reservation system
             #TODO put the granularity in network instead SA 18/07/12
                if attribute is 'granularity' :
                    granularity = node['granularity']
                    if granularity:
                        node_elem.add_instance('granularity', \
                                    granularity, granularity.fields)
                
          
            # set available element
                if attribute is 'boot_state':
                    if node.get('boot_state').lower() == 'alive':
                        available_elem = node_elem.add_element('available', \
                                                                    now='true')
                    else:
                        available_elem = node_elem.add_element('available', \
                                                                now='false')

            #set position 
                if attribute is 'position':
                    node_elem.add_instance('position', node['position'], \
                                                        SlabPosition.fields)
            ## add services
            #PGv2Services.add_services(node_elem, node.get('services', [])) 
            # add slivers
                if attribute is 'slivers':
                    slivers = node.get('slivers', [])
                    if not slivers:
                    # we must still advertise the available sliver types
                        slivers = Sliver({'type': 'slab-node'})
                    # we must also advertise the available initscripts
                    #slivers['tags'] = []
                    #if node.get('pl_initscripts'): 
                        #for initscript in node.get('pl_initscripts', []):
                            #slivers['tags'].append({'name': 'initscript', \
                                                    #'value': initscript['name']})
           
                    Slabv1Sliver.add_slivers(node_elem, slivers)
        return node_elems
                    

            
    @staticmethod
    def get_nodes(xml, filter={}):
        xpath = '//node%s | //default:node%s' % (XpathFilter.xpath(filter), \
                                                    XpathFilter.xpath(filter))
        node_elems = xml.xpath(xpath)  
        return Slabv1Node.get_node_objs(node_elems)

    @staticmethod 
    def get_nodes_with_slivers(xml, sliver_filter={}):

        xpath = '//node[count(sliver)>0] | \
                                //default:node[count(default:sliver) > 0]' 
        node_elems = xml.xpath(xpath)    
        logger.debug("SLABV1NODE \tget_nodes_with_slivers  \
                                node_elems %s"%(node_elems))
        return Slabv1Node.get_node_objs(node_elems)

    @staticmethod
    def get_node_objs(node_elems):
        nodes = []
        for node_elem in node_elems:
            node = Node(node_elem.attrib, node_elem)
            nodes.append(node) 
            if 'component_id' in node_elem.attrib:
                node['authority_id'] = \
                    Xrn(node_elem.attrib['component_id']).get_authority_urn()
            
            # get hardware types
            hardware_type_elems = node_elem.xpath('./default:hardware_type | \
                                                            ./hardware_type')
            node['hardware_types'] = [hw_type.get_instance(HardwareType) \
                                            for hw_type in hardware_type_elems]
            
            # get location
            location_elems = node_elem.xpath('./default:location | ./location')
            locations = [location_elem.get_instance(Location) \
                                            for location_elem in location_elems]
            if len(locations) > 0:
                node['location'] = locations[0]

            # get interfaces
            iface_elems = node_elem.xpath('./default:interface | ./interface')
            node['interfaces'] = [iface_elem.get_instance(Interface) \
                                            for iface_elem in iface_elems]

            # get services
            #node['services'] = PGv2Services.get_services(node_elem)

            # get slivers
            node['slivers'] = Slabv1Sliver.get_slivers(node_elem)    
            available_elems = node_elem.xpath('./default:available | \
                                                                ./available')
            if len(available_elems) > 0 and 'name' in available_elems[0].attrib:
                if available_elems[0].attrib.get('now', '').lower() == 'true': 
                    node['boot_state'] = 'boot'
                else: 
                    node['boot_state'] = 'disabled' 
                    
        logger.debug("SLABV1NODE \tget_nodes_objs  \
                                #nodes %s"%(nodes))
        return nodes


    @staticmethod
    def add_slivers(xml, slivers):
        logger.debug("SLABv1NODE \tadd_slivers ")
        component_ids = []
        for sliver in slivers:
            filter_sliver = {}
            if isinstance(sliver, str):
                filter_sliver['component_id'] = '*%s*' % sliver
                sliver = {}
            elif 'component_id' in sliver and sliver['component_id']:
                filter_sliver['component_id'] = '*%s*' % sliver['component_id']
            if not filter_sliver: 
                continue
            nodes = Slabv1Node.get_nodes(xml, filter_sliver)
            if not nodes:
                continue
            node = nodes[0]
            Slabv1Sliver.add_slivers(node, sliver)

    @staticmethod
    def remove_slivers(xml, hostnames):
        for hostname in hostnames:
            nodes = Slabv1Node.get_nodes(xml, \
                                    {'component_id': '*%s*' % hostname})
            for node in nodes:
                slivers = Slabv1Sliver.get_slivers(node.element)
                for sliver in slivers:
                    node.element.remove(sliver.element) 

        
                                    
