#!/usr/bin/python
from sfa.util.xrn import Xrn, hrn_to_urn, urn_to_hrn, urn_to_sliver_id
from sfa.util.sfatime import epochparse

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import Node
from sfa.rspecs.elements.link import Link
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.elements.services import Services
from sfa.rspecs.elements.pltag import PLTag
from sfa.rspecs.version_manager import VersionManager

from sfa.util.plxrn import PlXrn, hostname_to_urn, hrn_to_pl_slicename
from sfa.plc.vlink import get_tc_rate
from sfa.plc.topology import Topology


class PlAggregate:

    def __init__(self, driver):
        self.driver = driver
        self.user_options = {}
 
    def get_sites(self, filter={}):
        sites = {}
        for site in self.driver.GetSites(filter):
            sites[site['site_id']] = site
        return sites

    def get_interfaces(self, filter={}):
        interfaces = {}
        for interface in self.driver.GetInterfaces(filter):
            iface = Interface()
            if interface['bwlimit']:
                interface['bwlimit'] = str(int(interface['bwlimit'])/1000)
            interfaces[interface['interface_id']] = interface
        return interfaces

    def get_links(self, sites, nodes, interfaces):
        
        topology = Topology() 
        links = []
        for (site_id1, site_id2) in topology:
            site_id1 = int(site_id1)
            site_id2 = int(site_id2)
            link = Link()
            if not site_id1 in sites or site_id2 not in sites:
                continue
            site1 = sites[site_id1]
            site2 = sites[site_id2]
            # get hrns
            site1_hrn = self.driver.hrn + '.' + site1['login_base']
            site2_hrn = self.driver.hrn + '.' + site2['login_base']

            for s1_node_id in site1['node_ids']:
                for s2_node_id in site2['node_ids']:
                    if s1_node_id not in nodes or s2_node_id not in nodes:
                        continue
                    node1 = nodes[s1_node_id]
                    node2 = nodes[s2_node_id]
                    # set interfaces
                    # just get first interface of the first node
                    if1_xrn = PlXrn(auth=self.driver.hrn, interface='node%s:eth0' % (node1['node_id']))
                    if1_ipv4 = interfaces[node1['interface_ids'][0]]['ip']
                    if2_xrn = PlXrn(auth=self.driver.hrn, interface='node%s:eth0' % (node2['node_id']))
                    if2_ipv4 = interfaces[node2['interface_ids'][0]]['ip']

                    if1 = Interface({'component_id': if1_xrn.urn, 'ipv4': if1_ipv4} )
                    if2 = Interface({'component_id': if2_xrn.urn, 'ipv4': if2_ipv4} )

                    # set link
                    link = Link({'capacity': '1000000', 'latency': '0', 'packet_loss': '0', 'type': 'ipv4'})
                    link['interface1'] = if1
                    link['interface2'] = if2
                    link['component_name'] = "%s:%s" % (site1['login_base'], site2['login_base'])
                    link['component_id'] = PlXrn(auth=self.driver.hrn, interface=link['component_name']).get_urn()
                    link['component_manager_id'] =  hrn_to_urn(self.driver.hrn, 'authority+am')
                    links.append(link)

        return links

    def get_node_tags(self, filter={}):
        node_tags = {}
        for node_tag in self.driver.GetNodeTags(filter):
            node_tags[node_tag['node_tag_id']] = node_tag
        return node_tags

    def get_pl_initscripts(self, filter={}):
        pl_initscripts = {}
        filter.update({'enabled': True})
        for initscript in self.driver.GetInitScripts(filter):
            pl_initscripts[initscript['initscript_id']] = initscript
        return pl_initscripts


    def get_slice_and_slivers(self, slice_xrn):
        """
        Returns a dict of slivers keyed on the sliver's node_id
        """
        slivers = {}
        slice = None
        if not slice_xrn:
            return (slice, slivers)
        slice_urn = hrn_to_urn(slice_xrn, 'slice')
        slice_hrn, _ = urn_to_hrn(slice_xrn)
        slice_name = hrn_to_pl_slicename(slice_hrn)
        slices = self.driver.GetSlices(slice_name)
        if not slices:
            return (slice, slivers)
        slice = slices[0]

        # sort slivers by node id    
        for node_id in slice['node_ids']:
            sliver = Sliver({'sliver_id': urn_to_sliver_id(slice_urn, slice['slice_id'], node_id),
                             'name': slice['name'],
                             'type': 'plab-vserver', 
                             'tags': []})
            slivers[node_id]= sliver

        # sort sliver attributes by node id    
        tags = self.driver.GetSliceTags({'slice_tag_id': slice['slice_tag_ids']})
        for tag in tags:
            # most likely a default/global sliver attribute (node_id == None)
            if tag['node_id'] not in slivers:
                sliver = Sliver({'sliver_id': urn_to_sliver_id(slice_urn, slice['slice_id'], ""),
                                 'name': 'plab-vserver',
                                 'tags': []})
                slivers[tag['node_id']] = sliver
            slivers[tag['node_id']]['tags'].append(tag)
        
        return (slice, slivers)

    def get_nodes_and_links(self, slice=None,slivers=[], options={}):
        filter = {}
        tags_filter = {}
        if slice and 'node_ids' in slice and slice['node_ids']:
            filter['node_id'] = slice['node_ids']
            tags_filter=filter.copy()

        geni_available = options.get('geni_available')    
        if geni_available:
            filter['boot_state'] = 'boot'     
        
        filter.update({'peer_id': None})
        nodes = self.driver.GetNodes(filter)
       
        site_ids = []
        interface_ids = []
        tag_ids = []
        nodes_dict = {}
        for node in nodes:
            site_ids.append(node['site_id'])
            interface_ids.extend(node['interface_ids'])
            tag_ids.extend(node['node_tag_ids'])
            nodes_dict[node['node_id']] = node
 
        # get sites
        sites_dict  = self.get_sites({'site_id': site_ids}) 
        # get interfaces
        interfaces = self.get_interfaces({'interface_id':interface_ids}) 
        # get tags
        node_tags = self.get_node_tags(tags_filter)
        # get initscripts
        pl_initscripts = self.get_pl_initscripts()
        
        links = self.get_links(sites_dict, nodes_dict, interfaces)

        rspec_nodes = []
        for node in nodes:
            # skip whitelisted nodes
            if node['slice_ids_whitelist']:
                if not slice or slice['slice_id'] not in node['slice_ids_whitelist']:
                    continue
            rspec_node = Node()
            # xxx how to retrieve site['login_base']
            site_id=node['site_id']
            site=sites_dict[site_id]
            rspec_node['component_id'] = hostname_to_urn(self.driver.hrn, site['login_base'], node['hostname'])
            rspec_node['component_name'] = node['hostname']
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
            rspec_node['authority_id'] = hrn_to_urn(PlXrn.site_hrn(self.driver.hrn, site['login_base']), 'authority+sa')
            rspec_node['boot_state'] = node['boot_state']
            rspec_node['exclusive'] = 'False'
            rspec_node['hardware_types']= [HardwareType({'name': 'plab-pc'}),
                                           HardwareType({'name': 'pc'})]
            # only doing this because protogeni rspec needs
            # to advertise available initscripts 
            rspec_node['pl_initscripts'] = pl_initscripts.values()
             # add site/interface info to nodes.
            # assumes that sites, interfaces and tags have already been prepared.
            site = sites_dict[node['site_id']]
            if site['longitude'] and site['latitude']:  
                location = Location({'longitude': site['longitude'], 'latitude': site['latitude']})
                rspec_node['location'] = location
            rspec_node['interfaces'] = []
            if_count=0
            for if_id in node['interface_ids']:
                interface = Interface(interfaces[if_id]) 
                interface['ipv4'] = interface['ip']
                interface['component_id'] = PlXrn(auth=self.driver.hrn, 
                                                  interface='node%s:eth%s' % (node['node_id'], if_count)).get_urn()
                # interfaces in the manifest need a client id
                if slice:
                    interface['client_id'] = "%s:%s" % (node['node_id'], if_id)            
                rspec_node['interfaces'].append(interface)
                if_count+=1

            tags = [PLTag(node_tags[tag_id]) for tag_id in node['node_tag_ids']]
            rspec_node['tags'] = tags
            if node['node_id'] in slivers:
                # add sliver info
                sliver = slivers[node['node_id']]
                rspec_node['sliver_id'] = sliver['sliver_id']
                rspec_node['client_id'] = node['hostname']
                rspec_node['slivers'] = [sliver]
                
                # slivers always provide the ssh service
                login = Login({'authentication': 'ssh-keys', 'hostname': node['hostname'], 'port':'22'})
                service = Services({'login': login})
                rspec_node['services'] = [service]
            rspec_nodes.append(rspec_node)
        return (rspec_nodes, links)
             
        
    def get_rspec(self, slice_xrn=None, version = None, options={}):

        version_manager = VersionManager()
        version = version_manager.get_version(version)
        if not slice_xrn:
            rspec_version = version_manager._get_version(version.type, version.version, 'ad')
        else:
            rspec_version = version_manager._get_version(version.type, version.version, 'manifest')

        slice, slivers = self.get_slice_and_slivers(slice_xrn)
        rspec = RSpec(version=rspec_version, user_options=options)
        if slice and 'expires' in slice:
            rspec.xml.set('expires',  epochparse(slice['expires']))

        nodes, links = self.get_nodes_and_links(slice, slivers)
        rspec.version.add_nodes(nodes)
        rspec.version.add_links(links)
        
        # add sliver defaults
        default_sliver = slivers.get(None, [])
        if default_sliver:
            default_sliver_attribs = default_sliver.get('tags', [])
            for attrib in default_sliver_attribs:
                logger.info(attrib)
                rspec.version.add_default_sliver_attribute(attrib['tagname'], attrib['value'])
        return rspec.toxml()


