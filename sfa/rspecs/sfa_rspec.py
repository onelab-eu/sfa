#!/usr/bin/python 
from lxml import etree
from StringIO import StringIO
from sfa.rspecs.rspec import RSpec 
from sfa.util.xrn import *
from sfa.util.plxrn import hostname_to_urn
from sfa.util.config import Config
from sfa.rspecs.rspec_version import RSpecVersion  


_version = { 'type': 'sfa', 
             'version': '1' 
}

sfa_rspec_version = RSpecVersion(_version)

class SfaRSpec(RSpec):
    xml = None
    header = '<?xml version="1.0"?>\n'
    version = sfa_rspec_version

    ###################
    # Parser
    ###################
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
            if name.text == hostname:
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
        return nodes

    def get_nodes_with_slivers(self, network = None):
        if network:
            return self.xml.xpath('//network[@name="%s"]//node[sliver]/hostname/text()' % network)   
        else:
            return self.xml.xpath('//node[sliver]/hostname/text()')

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
                opts.append((e.tag, e.text))
        return opts

    def get_default_sliver_attributes(self, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)        
        else:
            defaults = self.xml.xpath("//network/sliver_defaults" % network)
        return self.attributes_list(defaults)

    def get_sliver_attributes(self, hostname, network=None):
        node = self.get_node_element(hostname, network)
        sliver = node.find("sliver")
        return self.attributes_list(sliver)

    def get_site_nodes(self, siteid, network=None):
        if network:
            nodes = self.xml.xpath('//network[@name="%s"]/site[@id="%s"]/node/hostname/text()' % \
                                    (network, siteid))
        else:
            nodes = self.xml.xpath('//site[@id="%s"]/node/hostname/text()' % siteid)
        return nodes
        
    def get_links(self, network=None):
        if network: 
            links = self.xml.xpath('//network[@name="%s"]/link' % network)
        else:
            links = self.xml.xpath('//link')    
        linklist = []
        for link in links:
            (end1, end2) = link.get("endpoints").split()
            name = link.find("description")
            linklist.append((name.text,
                             self.get_site_nodes(end1, network),
                             self.get_site_nodes(end2, network)))
        return linklist

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
        network_tag = etree.SubElement(self.xml, 'network', id=network)     

    def add_nodes(self, nodes, network = None, no_dupes=False):
        if not isinstance(nodes, list):
            nodes = [nodes]
        for node in nodes:
            if no_dupes and \
              self.get_node_element(node['hostname']):
                # node already exists
                continue

            network_tag = self.xml
            if 'network' in node:
                network = node['network']
                network_tags = self.xml.xpath('//network[@name="%s"]' % network)
                if not network_tags:
                    network_tag = etree.SubElement(self.xml, 'network', name=network)
                else:
                    network_tag = network_tags[0]
                     
            node_tag = etree.SubElement(network_tag, 'node')
            if 'network' in node:
                node_tag.set('component_manager_id', network)
            if 'urn' in node:
                node_tag.set('component_id', node['urn']) 
            if 'site_urn' in node:
                node_tag.set('site_id', node['site_urn'])
            if 'node_id' in node: 
                node_tag.set('node_id', 'n'+str(node['node_id']))
            if 'hostname' in node:
                hostname_tag = etree.SubElement(node_tag, 'hostname').text = node['hostname']
            if 'interfaces' in node:
                for interface in node['interfaces']:
                    if 'bwlimit' in interface and interface['bwlimit']:
                        bwlimit = etree.SubElement(node_tag, 'bw_limit', units='kbps').text = str(interface['bwlimit']/1000)
            if 'tags' in node:
                for tag in node['tags']:
                    #expose this hard wired list of tags, plus the ones that are marked 'sfa' in their category 
                    #if tag['tagname'] in ['fcdistro', 'arch'] or 'sfa' in tag['category'].split('/'):
                        #tag_element = etree.SubElement(node_tag, tag['tagname'], value=tag['value'])

		    #panos expose tags only if requested by the user using the -i option
		    if self.user_options:
		    	#print "[sfa rspec] found tag ",tag," and have info ",self.user_options.get('info')
		    	if self.user_options.get('info') and tag['tagname'] in self.user_options.get('info'):
                            tag_element = etree.SubElement(node_tag, tag['tagname'], value=tag['value'])

                    if 'sfa' in tag['category'].split('/'):
                        tag_element = etree.SubElement(node_tag, tag['tagname'], value=tag['value'])

            if 'site' in node:
                longitude = str(node['site']['longitude'])
                latitude = str(node['site']['latitude'])
                location = etree.SubElement(node_tag, 'location', country='unknown', \
                                            longitude=longitude, latitude=latitude)                

    def add_interfaces(self, interfaces):
        pass     

    def add_links(self, links):
        pass
    
    def add_slivers(self, slivers, network=None, no_dupes=False):
        if not isinstance(slivers, list):
            slivers = [slivers]

        nodes_with_slivers = self.get_nodes_with_slivers(network)
        for sliver in slivers:
            if sliver['hostname'] in nodes_with_slivers:
                continue
            node_elem = self.get_node_element(sliver['hostname'], network)
            sliver_elem = etree.SubElement(node_elem, 'sliver')
            if 'tags' in sliver:
                for tag in sliver['tags']:
                    etree.SubElement(sliver_elem, tag['tagname'], value=tag['value'])

    def remove_slivers(self, slivers, network=None, no_dupes=False):
        if not isinstance(slivers, list):
            slivers = [slivers]
        for sliver in slivers:
            node_elem = self.get_node_element(sliver['hostname'], network)
            sliver_elem = node.find('sliver')
            if sliver_elem != None:
                node_elem.remove(sliver)                 
    
    def add_default_sliver_attribute(self, name, value, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults" % network)
        if defaults is None:
            defaults = etree.Element("sliver_defaults")
            network = self.xml.xpath("//network[@name='%s']" % network)
            network.insert(0, defaults)
        self.add_attribute(defaults, name, value)

    def add_sliver_attribute(self, hostname, name, value, network=None):
        node = self.get_node_element(hostname, network)
        sliver = node.find("sliver")
        self.add_attribute(sliver, name, value)

    def remove_default_sliver_attribute(self, name, value, network=None):
        if network:
            defaults = self.xml.xpath("//network[@name='%s']/sliver_defaults" % network)
        else:
            defaults = self.xml.xpath("//sliver_defaults" % network)
        self.remove_attribute(defaults, name, value)

    def remove_sliver_attribute(self, hostname, name, value, network=None):
        node = self.get_node_element(hostname, network)
        sliver = node.find("sliver")
        self.remove_attribute(sliver, name, value)

    def add_vlink(self, fromhost, tohost, kbps, network=None):
        fromnode = self.get_node_element(fromhost, network)
        tonode = self.get_node_element(tohost, network)
        links = self.get_link(fromnode, tonode, network)

        for link in links:
            vlink = etree.SubElement(link, "vlink")
            fromid = fromnode.get("id")
            toid = tonode.get("id")
            vlink.set("endpoints", "%s %s" % (fromid, toid))
            self.add_attribute(vlink, "kbps", kbps)


    def remove_vlink(self, endpoints, network=None):
        vlinks = self.query_vlinks(endpoints, network)
        for vlink in vlinks:
            vlink.getparent().remove(vlink)


    def merge(self, in_rspec):
        """
        Merge contents for specified rspec with current rspec 
        """

        # just copy over all networks
        current_networks = self.get_networks()
        rspec = SfaRSpec(rspec=in_rspec)
        networks = rspec.get_network_elements()
        for network in networks:
            current_network = network.get('name')
            if not current_network in current_networks:
                self.xml.append(network)
                current_networks.append(current_network)
        
         

if __name__ == '__main__':
    rspec = SfaRSpec()
    nodes = [
    {'network': 'plc',
     'hostname': 'node1.planet-lab.org',
     'site_urn': 'urn:publicid:IDN+plc+authority+cm',
      'node_id': 1,
    },
    {'network': 'plc',
     'hostname': 'node2.planet-lab.org',
     'site_urn': 'urn:publicid:IDN+plc+authority+cm',
      'node_id': 1,
    },
    {'network': 'ple',
     'hostname': 'node1.planet-lab.eu',
     'site_urn': 'urn:publicid:IDN+plc+authority+cm',
      'node_id': 1,
    },
    ]
    rspec.add_nodes(nodes)
    print rspec
