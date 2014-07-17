from sfa.util.xrn import Xrn
from sfa.util.xml import XmlElement

from sfa.rspecs.elements.element    import Element
from sfa.rspecs.elements.port       import Port

class Ofeliav1Port:

    @staticmethod
    def add_portrs(xml, ports):
        raise Exception, "not implemented yet"
        if not ports:
            return
        if not isinstance(ports, list):
            ports = [ports]
        for port in ports:
            port_elem = xml.add_instance('port', port, ['name'])
            tags = port.get('tags', [])
            if tags:
                for tag in tags:
                    Ofeliav1Port.add_port_attribute(port_elem, tag['tagname'], tag['value'])

    @staticmethod
    def add_port_attribute(xml, name, value):
        raise Exception, "not implemented yet"
        elem = xml.add_element(name)
        elem.set_text(value)
    
    @staticmethod
    def get_port_attributes(xml):
        attribs = []
        for elem in xml.iterchildren():
            if elem.tag not in Port.fields:
                xml_element = XmlElement(elem, xml.namespaces)
                instance = Element(fields=xml_element, element=elem)
                instance['name'] = elem.tag
                instance['value'] = elem.text
                attribs.append(instance)
        return attribs 
                
    @staticmethod
    def get_ports(xml, filter=None):
        if filter is None: filter={}
        xpath = './openflow:port | ./port'
        port_elems = xml.xpath(xpath)
        ports = []
        for port_elem in port_elems:
            port = Port(port_elem.attrib,port_elem)
            #if 'component_id' in xml.attrib:     
            #    port['component_id'] = xml.attrib['component_id']
            #port['tags'] = Ofeliav1Port.get_port_attributes(port_elem)
            ports.append(port)
        return ports           

