from sfa.util.xrn import Xrn, get_leaf
from sfa.util.xml import XpathFilter

from sfa.rspecs.elements.node import NodeElement
from sfa.rspecs.elements.versions.korenv1SliverType import Korenv1SliverType
from sfa.rspecs.elements.granularity import Granularity

class Korenv1Node:

    @staticmethod
    def add_nodes(xml, nodes, rspec_content_type=None):
        node_elems = []
        for node in nodes:
            node_fields = ['component_manager_id', 'component_id', 'exclusive']
            node_elem = xml.add_instance('node', node, node_fields)

            # set granularity
            if node.get('exclusive') == "true":
                granularity = node.get('granularity')
                node_elem.add_instance('granularity', granularity, Granularity.fields)

            # set available element
            if node.get('available'):
                node_elem.add_element('available', now=node['available'])

            # add slivers
            slivers = node.get('slivers', [])
            Korenv1SliverType.add_os_slivers(node_elem, slivers)
            
            node_elems.append(node_elem)
        return node_elems

    @staticmethod
    def get_nodes(xml, filter=None):
        if filter is None: filter={}
        xpath = '//node%s | //default:node%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
        node_elems = xml.xpath(xpath)
        return Korenv1Node.get_node_objs(node_elems)

    @staticmethod
    def get_nodes_with_slivers(xml, filter=None):
        if filter is None: filter={}
        xpath = '//node[count(sliver)>0] | //default:node[count(openstack:sliver) > 0]' 
        node_elems = xml.xpath(xpath)        
        return Korenv1Node.get_node_objs(node_elems) 

    @staticmethod
    def get_node_objs(node_elems):
        nodes=[]
        for node_elem in node_elems:
            node = NodeElement(node_elem.attrib, node_elem)
            # Get the Openstack node objects from the requested rspec
            node['slivers'] = Korenv1SliverType.get_os_slivers(node_elem)
            nodes.append(node)
        return nodes


if __name__ == '__main__':
    from sfa.rspecs.rspec import RSpec
    r = RSpec('/tmp/koren_node.rspec')
    r2 = RSpec(version = 'KOREN')
    nodes = Korenv1Node.get_nodes(r.xml)
    Korenv1Node.add_nodes(r2.xml.root, nodes)
