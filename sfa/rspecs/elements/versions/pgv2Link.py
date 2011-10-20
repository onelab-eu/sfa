from lxml import etree
from sfa.rspecs.elements.link import Link
from sfa.rspecs.elements.interface import Interface

class PGv2Link:
    
    @staticmethod
    def add_links(xml, links):
        for link in links:
            link_elem = etree.SubElement(xml, 'link')
            for attrib in ['component_name', 'component_id', 'client_id']:
                if attrib in link and link[attrib]:
                    link_elem.set(attrib, link[attrib])
            if 'component_manager' in link and link['component_manger']:
                cm_element = etree.SubElement(xml, 'component_manager', name=link['component_manager'])
            if_ref1 = etree.SubElement(xml, 'interface_ref', component_id=link['interface1']['component_id'])
            if_ref2 = etree.SubElement(xml, 'interface_ref', component_id=link['interface2']['component_id'])
            prop1 = etree.SubElement(xml, 'property', source_id = link['interface1']['component_id'],
                dest_id = link['interface2']['component_id'], capacity=link['capacity'], 
                latency=link['latency'], packet_loss=link['packet_loss'])
            prop2 = etree.SubElement(xml, 'property', source_id = link['interface2']['component_id'],
                dest_id = link['interface1']['component_id'], capacity=link['capacity'], 
                latency=link['latency'], packet_loss=link['packet_loss'])
            if 'type' in link and link['type']:
                type_elem = etree.SubElement(xml, 'link_type', name=link['type'])             
             
    @staticmethod 
    def get_links(xml, namespaces=None):
        links = []
        link_elems = xml.xpath('//default:link', namespaces=namespaces)
        for link_elem in link_elems:
            # set client_id, component_id, component_name
            link = Link(link_elem.attrib)
            # set component manager
            cm = link_elem.xpath('./default:component_manager', namespaces=namespaces)
            if len(cm) >  0:
                cm = cm[0]
                if  'name' in cm.attrib:
                    link['component_manager'] = cm.attrib['name'] 
            # set link type
            link_types = link_elem.xpath('./default:link_type', namespaces=namespaces)
            if len(link_types) > 0:
                link_type = link_types[0]
                if 'name' in link_type.attrib:
                    link['type'] = link_type.attrib['name']
          
            # get capacity, latency and packet_loss and interfaces from first property  
            props = link_elem.xpath('./default:property', namespaces=namespaces)
            if len(props) > 0:
                prop = props[0]
                if 'source_id' in prop.attrib:
                    link['interface1'] = Interface({'component_id': prop.attrib['source_id']}) 
                if 'dest_id' in prop.attrib:
                    link['interface2'] = Interface({'component_id': prop.attrib['dest_id']})
                for attrib in ['capacity', 'latency', 'packet_loss']:
                    if attrib in prop.attrib:
                        link[attrib] = prop.attrib[attrib]
            links.append(link)
        return links 
            
        
