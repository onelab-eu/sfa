from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.sliver import Sliver

class PGv2SliverType:

    @staticmethod
    def add_sliver(xml, sliver):
        sliver_elem = Element.add(xml, 'sliver_type', sliver, ['name'])
                    
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
