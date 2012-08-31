#!/usr/bin/python
from sfa.util.xrn import Xrn, hrn_to_urn, urn_to_hrn, urn_to_sliver_id
from sfa.util.sfatime import utcparse, datetime_to_string
from sfa.util.sfalogging import logger

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import Node
from sfa.rspecs.elements.link import Link
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.position_3d import Position3D
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.elements.services import Services
from sfa.rspecs.elements.pltag import PLTag
from sfa.rspecs.elements.lease import Lease
from sfa.rspecs.elements.granularity import Granularity
from sfa.rspecs.elements.channel import Channel
from sfa.rspecs.version_manager import VersionManager

from sfa.nitos.nitosxrn import NitosXrn, hostname_to_urn, hrn_to_nitos_slicename, slicename_to_hrn
from sfa.planetlab.vlink import get_tc_rate
from sfa.planetlab.topology import Topology

import time

class NitosAggregate:

    def __init__(self, driver):
        self.driver = driver
 
    def get_sites(self, filter={}):
        sites = {}
        for site in self.driver.shell.GetSites(filter):
            sites[site['site_id']] = site
        return sites

    def get_interfaces(self, filter={}):
        interfaces = {}
        for interface in self.driver.shell.GetInterfaces(filter):
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
        for node_tag in self.driver.shell.GetNodeTags(filter):
            node_tags[node_tag['node_tag_id']] = node_tag
        return node_tags

    def get_pl_initscripts(self, filter={}):
        pl_initscripts = {}
        filter.update({'enabled': True})
        for initscript in self.driver.shell.GetInitScripts(filter):
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
        slice_name = hrn_to_nitos_slicename(slice_hrn)
        slices = self.driver.shell.getSlices()
        # filter results
        for slc in slices:
             if slc['slice_name'] == slice_name:
                 slice = slc
                 break

        if not slice:
            return (slice, slivers)
      
        reserved_nodes = self.driver.shell.getReservedNodes()
        # filter results
        for node in reserved_nodes:
             if node['slice_id'] == slice['slice_id']:
                 slivers[node[node_id]] = node

        return (slice, slivers)
       


    def get_nodes_and_links(self, slice_xrn, slice=None,slivers={}, options={}):
        # if we are dealing with a slice that has no node just return 
        # and empty list    
        if slice_xrn:
            if not slice or not slivers:
                return ([],[])
            else:
                nodes = [slivers[sliver] for sliver in slivers]
        else:
            nodes = self.driver.shell.getNodes()
        
        # get the granularity in second for the reservation system
        grain = self.driver.testbedInfo['grain']
        #grain = 1800
       
 

        rspec_nodes = []
        for node in nodes:
            rspec_node = Node()
            site_name = self.driver.testbedInfo['name']
            rspec_node['component_id'] = hostname_to_urn(self.driver.hrn, site_name, node['name'])
            rspec_node['component_name'] = node['name']
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
            rspec_node['authority_id'] = hrn_to_urn(NitosXrn.site_hrn(self.driver.hrn, site_name), 'authority+sa')
            # do not include boot state (<available> element) in the manifest rspec
            #if not slice:     
            #    rspec_node['boot_state'] = node['boot_state']
            rspec_node['exclusive'] = 'true'
            # site location
            longitude = self.driver.testbedInfo['longitude']
            latitude = self.driver.testbedInfo['latitude']  
            if longitude and latitude:  
                location = Location({'longitude': longitude, 'latitude': latitude, 'country': 'unknown'})
                rspec_node['location'] = location
            # 3D position
            position_3d = Position3D({'x': node['position']['X'], 'y': node['position']['Y'], 'z': node['position']['Z']})
            #position_3d = Position3D({'x': 1, 'y': 2, 'z': 3})
            rspec_node['position_3d'] = position_3d 
            # Granularity
            granularity = Granularity({'grain': grain})
            rspec_node['granularity'] = granularity

            # HardwareType
            rspec_node['hardware_type'] = node['node_type']
            #rspec_node['hardware_type'] = "orbit"

                
            rspec_nodes.append(rspec_node)
        return (rspec_nodes, []) 

    def get_leases_and_channels(self, slice=None, options={}):
        
        slices = self.driver.shell.getSlices()
        nodes = self.driver.shell.getNodes()
        leases = self.driver.shell.getReservedNodes()
        channels = self.driver.shell.getChannels()
        reserved_channels = self.driver.shell.getReservedChannels()
        grain = self.driver.testbedInfo['grain']

        if slice:
            for lease in leases:
                 if lease['slice_id'] != slice['slice_id']:
                     leases.remove(lease)
            for channel in reserved_channels:
                 if channel['slice_id'] != slice['slice_id']:
                     reserved_channels.remove(channel)

        rspec_channels = []
        for channel in reserved_channels:
             
            rspec_channel = {}
            #retrieve channel number  
            for chl in channels:
                 if chl['channel_id'] == channel['channel_id']:
                     channel_number = chl['channel']
                     break

            rspec_channel['channel_num'] = channel_number
            rspec_channel['start_time'] = channel['start_time']
            rspec_channel['duration'] = (int(channel['end_time']) - int(channel['start_time'])) / int(grain)
                 
            # retreive slicename
            for slc in slices:
                 if slc['slice_id'] == channel['slice_id']:
                     slicename = slc['slice_name']
                     break

            slice_hrn = slicename_to_hrn(self.driver.hrn, self.driver.testbedInfo['name'], slicename)
            slice_urn = hrn_to_urn(slice_hrn, 'slice')
            rspec_channel['slice_id'] = slice_urn
            rspec_channels.append(rspec_channel)

 
        rspec_leases = []
        for lease in leases:

            rspec_lease = Lease()
            
            rspec_lease['lease_id'] = lease['reservation_id']
            # retreive node name
            for node in nodes:
                 if node['node_id'] == lease['node_id']:
                     nodename = node['name']
                     break
           
            rspec_lease['component_id'] = hostname_to_urn(self.driver.hrn, self.driver.testbedInfo['name'], nodename)
            # retreive slicename
            for slc in slices:
                 if slc['slice_id'] == lease['slice_id']:
                     slicename = slc['slice_name']
                     break
            
            slice_hrn = slicename_to_hrn(self.driver.hrn, self.driver.testbedInfo['name'], slicename)
            slice_urn = hrn_to_urn(slice_hrn, 'slice')
            rspec_lease['slice_id'] = slice_urn
            rspec_lease['start_time'] = lease['start_time']
            rspec_lease['duration'] = (int(lease['end_time']) - int(lease['start_time'])) / int(grain)
            rspec_leases.append(rspec_lease)

        return (rspec_leases, rspec_channels)


    def get_channels(self, options={}):
        
        filter = {}
        channels = self.driver.shell.getChannels()
        rspec_channels = []
        for channel in channels:
            rspec_channel = Channel()
            rspec_channel['channel_num'] = channel['channel']
            rspec_channel['frequency'] = channel['frequency']
            rspec_channel['standard'] = channel['modulation']
            rspec_channels.append(rspec_channel)
        return rspec_channels


    
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
            rspec.xml.set('expires',  datetime_to_string(utcparse(slice['expires'])))

        if not options.get('list_leases') or options.get('list_leases') and options['list_leases'] != 'leases':
           nodes, links = self.get_nodes_and_links(slice_xrn, slice, slivers, options)
           rspec.version.add_nodes(nodes)
           rspec.version.add_links(links)
           # add sliver defaults
           default_sliver = slivers.get(None, [])
           if default_sliver:
              default_sliver_attribs = default_sliver.get('tags', [])
              for attrib in default_sliver_attribs:
                  logger.info(attrib)
                  rspec.version.add_default_sliver_attribute(attrib['tagname'], attrib['value'])
           # add wifi channels
           channels = self.get_channels()
           rspec.version.add_channels(channels)

        if not options.get('list_leases') or options.get('list_leases') and options['list_leases'] != 'resources':
           leases, channels = self.get_leases_and_channels(slice)
           rspec.version.add_leases(leases, channels)

        return rspec.toxml()


