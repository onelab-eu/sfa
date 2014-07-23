from sfa.util.sfalogging import logger
from sfa.util.xml import XpathFilter
from sfa.util.xrn import Xrn, get_leaf

from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.link import Link

class Ofeliav1Link:

    @staticmethod
    def get_links(xml, filter=None):
        if filter is None: filter={}
        xpath = '//link%s | //openflow:link%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
        link_elems = xml.xpath(xpath)
        return Ofeliav1Link.get_link_objs(link_elems)

    @staticmethod
    def get_link_objs(link_elems):
        links = []    
        for link_elem in link_elems:
            link = Link(link_elem.attrib, link_elem)
            links.append(link)
        return links
