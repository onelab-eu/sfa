

from lxml import etree
from sfa.util.plxrn import PlXrn
from sfa.util.xrn import Xrn
from sfa.rspecs.rspec_elements import RSpecElement, RSpecElements

class SFAv1Network:
    elements = {
        'network': RSpecElement(RSpecElements.NETWORK, '//network'),
    }

    @staticmethod
    def add_network(xml, network):
        found = False
        network_objs = SFAv1Network.get_networks(xml)
        for network_obj in network_objs:
            if network_obj['name'] == network['name']:
                found = True
                network_elem = network_obj.element
        if not found:
            network_elem = etree.SubElement(xml, 'network', name = network['name'])
        return network_elem  
    
    @staticmethod
    def get_networks(xml):
        networks = []
        network_elems = xml.xpath(SFAv1Network.elements['network'].path)
        for network_elem in network_elems:
            network = Network({'name': network_elem.attrib.get('name', None)}, network_elem)
            networks.append(network)
        return networks
