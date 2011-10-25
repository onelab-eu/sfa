from lxml import etree
from sfa.rspecs.elements.link import Link
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.rspec_elements import RSpecElement, RSpecElements

class PGv2Link:

    elements = {
        'link': RSpecElement(RSpecElements.LINK, '//default:link | //link'),
        'component_manager': RSpecElement(RSpecElements.COMPONENT_MANAGER, './default:component_manager | ./component_manager'),
        'link_type': RSpecElement(RSpecElements.LINK_TYPE, './default:link_type | ./link_type'),
        'property': RSpecElement(RSpecElements.PROPERTY, './default:property | ./property'),
        'interface_ref': RSpecElement(RSpecElements.INTERFACE_REF, './default:interface_ref | ./interface_ref') 
    }
    
    @staticmethod
    def add_links(xml, links):
        root = xml.root
        for link in links:
            link_elem = etree.SubElement(root, 'link')
            for attrib in ['component_name', 'component_id', 'client_id']:
                if attrib in link and link[attrib]:
                    link_elem.set(attrib, link[attrib])
            if 'component_manager' in link and link['component_manager']:
                cm_element = etree.SubElement(link_elem, 'component_manager', name=link['component_manager'])
            for if_ref in [link['interface1'], link['interface2']]:
                if_ref_elem = etree.SubElement(link_elem, 'interface_ref')
                for attrib in Interface.fields:
                    if attrib in if_ref and if_ref[attrib]:
                        if_ref_elem.attrib[attrib] = if_ref[attrib]  
            prop1 = etree.SubElement(link_elem, 'property', source_id = link['interface1']['component_id'],
                dest_id = link['interface2']['component_id'], capacity=link['capacity'], 
                latency=link['latency'], packet_loss=link['packet_loss'])
            prop2 = etree.SubElement(link_elem, 'property', source_id = link['interface2']['component_id'],
                dest_id = link['interface1']['component_id'], capacity=link['capacity'], 
                latency=link['latency'], packet_loss=link['packet_loss'])
            if 'type' in link and link['type']:
                type_elem = etree.SubElement(link_elem, 'link_type', name=link['type'])             
   
    @staticmethod 
    def get_links(xml):
        links = []
        link_elems = xml.xpath(PGv2Link.elements['link'].path, namespaces=xml.namespaces)
        for link_elem in link_elems:
            # set client_id, component_id, component_name
            link = Link(link_elem.attrib)
            link['_element'] = link_elem
            # set component manager
            cm = link_elem.xpath('./default:component_manager', namespaces=xml.namespaces)
            if len(cm) >  0:
                cm = cm[0]
                if  'name' in cm.attrib:
                    link['component_manager'] = cm.attrib['name'] 
            # set link type
            link_types = link_elem.xpath(PGv2Link.elements['link_type'].path, namespaces=xml.namespaces)
            if len(link_types) > 0:
                link_type = link_types[0]
                if 'name' in link_type.attrib:
                    link['type'] = link_type.attrib['name']
          
            # get capacity, latency and packet_loss from first property  
            props = link_elem.xpath(PGv2Link.elements['property'].path, namespaces=xml.namespaces)
            if len(props) > 0:
                prop = props[0]
                for attrib in ['capacity', 'latency', 'packet_loss']:
                    if attrib in prop.attrib:
                        link[attrib] = prop.attrib[attrib]
                             
            # get interfaces 
            if_elems = link_elem.xpath(PGv2Link.elements['interface_ref'].path, namespaces=xml.namespaces)
            ifs = []
            for if_elem in if_elems:
                if_ref = Interface(if_elem.attrib)                 
                ifs.append(if_ref)
            if len(ifs) > 1:
                link['interface1'] = ifs[0]
                link['interface2'] = ifs[1] 
            links.append(link)
        return links 


    def add_link_requests(xml, links_tuple):
        available_links = PGv2Link.get_links(xml) 
           
