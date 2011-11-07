
from lxml import etree

from sfa.rspecs.elements.sliver import Sliver

from sfa.util.xrn import Xrn
from sfa.util.plxrn import PlXrn
class SFAv1Sliver:

    @staticmethod
    def add_slivers(xml, slivers):
        for sliver in slivers:
            sliver_elem = etree.SubElement(xml, 'sliver')
            if sliver.get('component_id'):
                name_full = Xrn(sliver.get('component_id')).get_leaf()
                name = name_full.split(':')
                sliver_elem.set('name', name)
                     
