from copy import deepcopy
from lxml import etree
from sfa.util.xrn import hrn_to_urn, urn_to_hrn
from sfa.util.plxrn import PlXrn
from sfa.rspecs.rspec_version import BaseVersion
from sfa.rspecs.rspec_elements import RSpecElement, RSpecElements
from sfa.rspecs.elements.versions.pgv2Link import PGv2Link

class SFAv1(BaseVersion):
    enabled = True
    type = 'SFA'
    content_type = '*'
    version = '1'
    schema = None
    namespace = None
    extensions = {}
    namespaces = None
    elements = [] 
    template = '<RSpec type="%s"></RSpec>' % type

    def get_network_elements(self):
        return self.xml.xpath('//network')

    def get_networks(self):
        return self.xml.xpath('//network[@name]/@name')

    def get_node_element(self, hostname, network=None):
        if network:
            names = self.xml.xpath('//network[@name="%s"]//node/hostname' % network)
        else:
            names = self.xml.xpath('//node/hostname')
        for name in names:
            if str(name.text).strip() == hostname:
                return name.getparent()
        return None

    def get_node_elements(self, network=None):
        if network:
            return self.xml.xpath('//network[@name="%s"]//node' % network)
        else:
            return self.xml.xpath('//node')

    def get_nodes(self, network=None):
        if network == None:
            nodes = self.xml.xpath('//node/hostname/text()')
        else:
            nodes = self.xml.xpath('//network[@name="%s"]//node/hostname/text()' % network)

        nodes = [node.strip() for node in nodes]
        return nodes

    def get_nodes_with_slivers(self, network = None):
        if network:
            nodes =  self.xml.xpath('//network[@name="%s"]//node[sliver]/hostname/text()' % network)  
        else:
            nodes = self.xml.xpath('//node[sliver]/hostname/text()')

        nodes = [node.strip() for node in nodes]
        return nodes

    def get_nodes_without_slivers(self, network=None):
        xpath_nodes_without_slivers = '//node[not(sliver)]/hostname/text()'
        xpath_nodes_without_slivers_in_network = '//network[@name="%s"]//node[not(sliver)]/hostname/text()'
        if network:
            return self.xml.xpath('//network[@name="%s"]//node[not(sliver)]/hostname/text()' % network)
        else:
            return self.xml.xpath('//node[not(sliver)]/hostname/text()')

    def attributes_list(self, elem):
        # convert a list of attribute tags into list of tuples
        # (tagnme, text_value)
        opts = []
        if elem is not None:
            for e in elem:
                opts.append((e.tag, str(e.text).strip()))
        return opts

    def get_default_sliver_attributes(self, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults")
        if isinstance(defaults, list) and defaults:
            defaults = defaults[0]
        return self.attributes_list(defaults)

    def get_sliver_attributes(self, hostname, network=None):
        attributes = []
        node = self.get_node_element(hostname, network)
        #sliver = node.find("sliver")
        slivers = node.xpath('./sliver')
        if isinstance(slivers, list) and slivers:
            attributes = self.attributes_list(slivers[0])
        return attributes

    def get_slice_attributes(self, network=None):
        slice_attributes = []
        nodes_with_slivers = self.get_nodes_with_slivers(network)
        for default_attribute in self.get_default_sliver_attributes(network):
            attribute = {'name': str(default_attribute[0]), 'value': str(default_attribute[1]), 'node_id': None}
            slice_attributes.append(attribute)
        for node in nodes_with_slivers:
            sliver_attributes = self.get_sliver_attributes(node, network)
            for sliver_attribute in sliver_attributes:
                attribute = {'name': str(sliver_attribute[0]), 'value': str(sliver_attribute[1]), 'node_id': node}
                slice_attributes.append(attribute)
        return slice_attributes

    def get_site_nodes(self, siteid, network=None):
        if network:
            nodes = self.xml.xpath('//network[@name="%s"]/site[@id="%s"]/node/hostname/text()' % \
                                    (network, siteid))
        else:
            nodes = self.xml.xpath('//site[@id="%s"]/node/hostname/text()' % siteid)
        return nodes

    def get_links(self, network=None):
        return PGv2Link.get_links(self.xml)

    def get_link_requests(self):
        return PGv2Link.get_link_requests(self.xml) 

    def get_link(self, fromnode, tonode, network=None):
        fromsite = fromnode.getparent()
        tosite = tonode.getparent()
        fromid = fromsite.get("id")
        toid = tosite.get("id")
        if network:
            query = "//network[@name='%s']" % network + "/link[@endpoints = '%s %s']"
        else:
            query = "//link[@endpoints = '%s %s']"

        results = self.rspec.xpath(query % (fromid, toid))
        if not results:
            results = self.rspec.xpath(query % (toid, fromid))
        return results

    def query_links(self, fromnode, tonode, network=None):
        return get_link(fromnode, tonode, network)

    def get_vlinks(self, network=None):
        vlinklist = []
        if network:
            vlinks = self.xml.xpath("//network[@name='%s']//vlink" % network)
        else:
            vlinks = self.xml.xpath("//vlink")
        for vlink in vlinks:
            endpoints = vlink.get("endpoints")
            (end1, end2) = endpoints.split()
            if network:
                node1 = self.xml.xpath('//network[@name="%s"]//node[@id="%s"]/hostname/text()' % \
                                       (network, end1))[0]
                node2 = self.xml.xpath('//network[@name="%s"]//node[@id="%s"]/hostname/text()' % \
                                       (network, end2))[0]
            else:
                node1 = self.xml.xpath('//node[@id="%s"]/hostname/text()' % end1)[0]
                node2 = self.xml.xpath('//node[@id="%s"]/hostname/text()' % end2)[0]
            desc = "%s <--> %s" % (node1, node2)
            kbps = vlink.find("kbps")
            vlinklist.append((endpoints, desc, kbps.text))
        return vlinklist

    def get_vlink(self, endponts, network=None):
        if network:
            query = "//network[@name='%s']//vlink[@endpoints = '%s']" % (network, endpoints)
        else:
            query = "//vlink[@endpoints = '%s']" % (network, endpoints)
        results = self.rspec.xpath(query)
        return results

    def query_vlinks(self, endpoints, network=None):
        return get_vlink(endpoints,network)

    
    ##################
    # Builder
    ##################

    def add_network(self, network):
        network_tags = self.xml.xpath('//network[@name="%s"]' % network)
        if not network_tags:
            network_tag = etree.SubElement(self.xml.root, 'network', name=network)
        else:
            network_tag = network_tags[0]
        return network_tag

    def add_nodes(self, nodes, network = None, no_dupes=False):
        if not isinstance(nodes, list):
            nodes = [nodes]
        for node in nodes:
            if no_dupes and \
              self.get_node_element(node['hostname']):
                # node already exists
                continue

            network_tag = self.xml.root
            if 'network' in node:
                network = node['network']
                network_tag = self.add_network(network)

            node_tag = etree.SubElement(network_tag, 'node')
            if 'network' in node:
                node_tag.set('component_manager_id', hrn_to_urn(network, 'authority+sa'))
            if 'urn' in node:
                node_tag.set('component_id', node['urn'])
            if 'site_urn' in node:
                node_tag.set('site_id', node['site_urn'])
            if 'node_id' in node:
                node_tag.set('node_id', 'n'+str(node['node_id']))
            if 'boot_state' in node:
                node_tag.set('boot_state', node['boot_state'])
            if 'hostname' in node:
                node_tag.set('component_name', node['hostname']) 
                hostname_tag = etree.SubElement(node_tag, 'hostname').text = node['hostname']
            if 'interfaces' in node:
                i = 0
                for interface in node['interfaces']:
                    if 'bwlimit' in interface and interface['bwlimit']:
                        bwlimit = etree.SubElement(node_tag, 'bw_limit', units='kbps').text = str(interface['bwlimit']/1000)
                    comp_id = PlXrn(auth=network, interface='node%s:eth%s' % (node['node_id'], i)).get_urn() 
                    ipaddr = interface['ip'] 
                    interface_tag = etree.SubElement(node_tag, 'interface', component_id=comp_id, ipv4=ipaddr)
                    i+=1
            if 'bw_unallocated' in node:
                bw_unallocated = etree.SubElement(node_tag, 'bw_unallocated', units='kbps').text = str(node['bw_unallocated']/1000) 
            if 'tags' in node:
                for tag in node['tags']:
                   # expose this hard wired list of tags, plus the ones that are marked 'sfa' in their category
                   if tag['tagname'] in ['fcdistro', 'arch'] or 'sfa' in tag['category'].split('/'):
                        tag_element = etree.SubElement(node_tag, tag['tagname']).text=tag['value']

            if 'site' in node:
                longitude = str(node['site']['longitude'])
                latitude = str(node['site']['latitude'])
                location = etree.SubElement(node_tag, 'location', country='unknown', \
                                            longitude=longitude, latitude=latitude)

    def merge_node(self, source_node_tag, network, no_dupes=False):
        if no_dupes and self.get_node_element(node['hostname']):
            # node already exists
            return

        network_tag = self.add_network(network)
        network_tag.append(deepcopy(source_node_tag))

    def add_interfaces(self, interfaces):
        pass

    def add_links(self, links):
        networks = self.get_network_elements()
        if len(networks) > 0:
            xml = networks[0]
        else:
            xml = self.xml    
        PGv2Link.add_links(xml, links)

    def add_link_requests(self, links):
        networks = self.get_network_elements()
        if len(networks) > 0:
            xml = networks[0]
        else:
            xml = self.xml 
        PGv2Link.add_link_requests(xml, links)

    def add_slivers(self, slivers, network=None, sliver_urn=None, no_dupes=False, append=False):
        # add slice name to network tag
        network_tags = self.xml.xpath('//network')
        if network_tags:
            network_tag = network_tags[0]
            network_tag.set('slice', urn_to_hrn(sliver_urn)[0])
        
        all_nodes = self.get_nodes()
        nodes_with_slivers = [sliver['hostname'] for sliver in slivers]
        nodes_without_slivers = set(all_nodes).difference(nodes_with_slivers)
        
        # add slivers
        for sliver in slivers:
            node_elem = self.get_node_element(sliver['hostname'], network)
            if not node_elem: continue
            sliver_elem = etree.SubElement(node_elem, 'sliver')
            if 'tags' in sliver:
                for tag in sliver['tags']:
                    etree.SubElement(sliver_elem, tag['tagname']).text = value=tag['value']
            
        # remove all nodes without slivers
        if not append:
            for node in nodes_without_slivers:
                node_elem = self.get_node_element(node)
                parent = node_elem.getparent()
                parent.remove(node_elem)

    def remove_slivers(self, slivers, network=None, no_dupes=False):
        for sliver in slivers:
            node_elem = self.get_node_element(sliver['hostname'], network)
            sliver_elem = node_elem.find('sliver')
            if sliver_elem != None:
                node_elem.remove(sliver_elem)

    def add_default_sliver_attribute(self, name, value, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults" % network)
        if not defaults :
            network_tag = self.xml.xpath("//network[@name='%s']" % network)
            if isinstance(network_tag, list):
                network_tag = network_tag[0]
            defaults = self.xml.add_element('sliver_defaults', attrs={}, parent=network_tag)
        elif isinstance(defaults, list):
            defaults = defaults[0]
        self.xml.add_attribute(defaults, name, value)

    def add_sliver_attribute(self, hostname, name, value, network=None):
        node = self.get_node_element(hostname, network)
        sliver = node.find("sliver")
        self.xml.add_attribute(sliver, name, value)

    def remove_default_sliver_attribute(self, name, value, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults" % network)
        self.xml.remove_attribute(defaults, name, value)

    def remove_sliver_attribute(self, hostname, name, value, network=None):
        node = self.get_node_element(hostname, network)
        sliver = node.find("sliver")
        self.xml.remove_attribute(sliver, name, value)

    def add_vlink(self, fromhost, tohost, kbps, network=None):
        fromnode = self.get_node_element(fromhost, network)
        tonode = self.get_node_element(tohost, network)
        links = self.get_link(fromnode, tonode, network)

        for link in links:
            vlink = etree.SubElement(link, "vlink")
            fromid = fromnode.get("id")
            toid = tonode.get("id")
            vlink.set("endpoints", "%s %s" % (fromid, toid))
            self.xml.add_attribute(vlink, "kbps", kbps)


    def remove_vlink(self, endpoints, network=None):
        vlinks = self.query_vlinks(endpoints, network)
        for vlink in vlinks:
            vlink.getparent().remove(vlink)


    def merge(self, in_rspec):
        """
        Merge contents for specified rspec with current rspec
        """

        from sfa.rspecs.rspec import RSpec
        if isinstance(in_rspec, RSpec):
            rspec = in_rspec
        else:
            rspec = RSpec(in_rspec)
        if rspec.version.type.lower() == 'protogeni':
            from sfa.rspecs.rspec_converter import RSpecConverter
            in_rspec = RSpecConverter.to_sfa_rspec(rspec.toxml())
            rspec = RSpec(in_rspec)

        # just copy over all networks
        current_networks = self.get_networks()
        networks = rspec.version.get_network_elements()
        for network in networks:
            current_network = network.get('name')
            if current_network and current_network not in current_networks:
                self.xml.root.append(network)
                current_networks.append(current_network)

if __name__ == '__main__':
    from sfa.rspecs.rspec import RSpec
    from sfa.rspecs.rspec_elements import *
    r = RSpec('/tmp/resources.rspec')
    r.load_rspec_elements(SFAv1.elements)
    print r.get(RSpecElements.NODE)
