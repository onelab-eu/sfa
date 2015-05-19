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
            Korenv1SliverType.add_slivers(node_elem, slivers)

            node_elems.append(node_elem)

        return node_elems

    @staticmethod
    def get_nodes(xml, filter=None):
        if filter is None: filter={}
        xpath = '//node%s | //default:node%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
        node_elems = xml.xpath(xpath)
        return Korenv1Node.get_openstack_node_objs(node_elems)

    @staticmethod
    def get_nodes_with_slivers(xml, filter=None):
        if filter is None: filter={}
        #TODO:openflow To count nodes for other resources, insert xpath for them.
        #TODO          We also update koren rspec file (korenv1.py)
        xpath = '//node[count(sliver)>0] | //default:node[count(openstack:sliver) > 0]' 
        node_elems = xml.xpath(xpath)        
        return Korenv1Node.get_openstack_node_objs(node_elems)

    @staticmethod
    def get_openstack_node_objs(node_elems):
        nodes=[]
        for node_elem in node_elems:
            node = NodeElement(node_elem.attrib, node_elem)
            if 'component_id' in node_elem.attrib:
                node['authority_id'] = Xrn(node_elem.attrib['component_id']).get_authority_urn()
            # Get slivers of Openstack
            node['slivers'] = Korenv1SliverType.get_os_slivers(node_elem)
            nodes.append(node)
        return nodes

    """
    @staticmethod
    def add_slivers(xml, slivers):
        component_ids = []
        for sliver in slivers:
            filter = {}
            if isinstance(sliver, str):
                filter['component_id'] = '*%s*' % sliver
                sliver = {}
            elif 'component_id' in sliver and sliver['component_id']:
                filter['component_id'] = '*%s*' % sliver['component_id']
            if not filter: 
                continue
            nodes = Korenv1Node.get_nodes(xml, filter)
            if not nodes:
                continue
            node = nodes[0]
            PGv2SliverType.add_slivers(node, sliver)

    @staticmethod
    def remove_slivers(xml, hostnames):
        for hostname in hostnames:
            nodes = Korenv1Node.get_nodes(xml, {'component_id': '*%s*' % hostname})
            for node in nodes:
                slivers = PGv2SliverType.get_slivers(node.element)
                for sliver in slivers:
                    node.element.remove(sliver.element)
    """

if __name__ == '__main__':
    from sfa.rspecs.rspec import RSpec
    r = RSpec('/tmp/koren_node.rspec')
    r2 = RSpec(version = 'KOREN')
    nodes = Korenv1Node.get_nodes(r.xml)
    Korenv1Node.add_nodes(r2.xml.root, nodes)
