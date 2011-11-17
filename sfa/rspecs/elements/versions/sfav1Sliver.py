from sfa.util.xrn import Xrn
from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.versions.sfav1PLTag import SFAv1PLTag

class SFAv1Sliver:

    @staticmethod
    def add_slivers(xml, slivers):
        if not slivers:
            return
        if not isinstance(slivers, list):
            slivers = [slivers]
        for sliver in slivers:
            sliver_elem = xml.add_instance('sliver', sliver, ['name'])
            SFAv1Sliver.add_sliver_attributes(sliver_elem, sliver.get('tags', []))
            if sliver.get('sliver_id'):
                sliver_id_leaf = Xrn(sliver.get('sliver_id')).get_leaf()
                sliver_id_parts = sliver_id_leaf.split(':')
                name = sliver_id_parts[0]
                sliver_elem.set('name', name)

    @staticmethod
    def add_sliver_attributes(xml, attributes):
        SFAv1PLTag.add_pl_tags(xml, attributes)
                    
    @staticmethod
    def get_slivers(xml, filter={}):
        xpath = './default:sliver | ./sliver'
        sliver_elems = xml.xpath(xpath)
        slivers = []
        for sliver_elem in sliver_elems:
            sliver = Sliver(sliver_elem.attrib,sliver_elem)
            if 'component_id' in xml.attrib:     
                sliver['component_id'] = xml.attrib['component_id']
            sliver['tags'] = SFAv1Sliver.get_sliver_attributes(sliver_elem)
            slivers.append(sliver)
        return slivers           

    @staticmethod
    def get_sliver_attributes(xml, filter={}):
        return SFAv1PLTag.get_pl_tags(xml, ignore=Sliver.fields)     
