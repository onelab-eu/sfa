from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.sliver import Sliver

class PGv2SliverType:

    @staticmethod
    def add_slivers(xml, sliver):
        if not isinstance(slivers, list):
            slivers = [slivers]
        for sliver in slivers: 
            sliver_elem = Element.add(xml, 'sliver_type', sliver, ['type', 'client_id'])
            for tag in sliver.get('tags', []):
                if tag['name'] == 'initscript':
                    sliver_elem.add_element('{%s}initscript' % xml.namespaces['planetlab'], name=tag['value'])
                    
    @staticmethod
    def get_slivers(xml, filter={}):
        xpath = './default:sliver_type | ./sliver_type'
        sliver_elems = xml.xpath(xpath)
        slivers = []
        for sliver_elem in sliver_elems:
            sliver = Sliver(sliver_elem.attrib,sliver_elm)
            if 'component_id' in xml.attrib:     
                sliver['component_id'] = xml.attrib['component_id']
            slivers.append(sliver)
        return slivers            
