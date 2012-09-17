#!/usr/bin/python
from sfa.util.xrn import Xrn, hrn_to_urn, urn_to_hrn
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
        slices = self.driver.shell.getSlices({'slice_name': slice_name}, [])
        #filter results
        for slc in slices:
             if slc['slice_name'] == slice_name:
                 slice = slc
                 break

        if not slice:
            return (slice, slivers)
      
        reserved_nodes = self.driver.shell.getReservedNodes({'slice_id': slice['slice_id']}, [])
        reserved_node_ids = []
        # filter on the slice
        for node in reserved_nodes:
             if node['slice_id'] == slice['slice_id']:
                 reserved_node_ids.append(node['node_id'])
        #get all the nodes
        all_nodes = self.driver.shell.getNodes({}, [])
       
        for node in all_nodes:
             if node['node_id'] in reserved_node_ids:
                 slivers[node['node_id']] = node
        
        return (slice, slivers)
       


    def get_nodes(self, slice_xrn, slice=None,slivers={}, options={}):
        # if we are dealing with a slice that has no node just return 
        # and empty list    
        if slice_xrn:
            if not slice or not slivers:
                return []
            else:
                nodes = [slivers[sliver] for sliver in slivers]
        else:
            nodes = self.driver.shell.getNodes({}, [])
        
        # get the granularity in second for the reservation system
        grain = self.driver.testbedInfo['grain']
        #grain = 1800
       

        rspec_nodes = []
        for node in nodes:
            rspec_node = Node()
            site_name = self.driver.testbedInfo['name']
            rspec_node['component_id'] = hostname_to_urn(self.driver.hrn, site_name, node['hostname'])
            rspec_node['component_name'] = node['hostname']
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
            
            #slivers
            if node['node_id'] in slivers:
                # add sliver info
                sliver = slivers[node['node_id']]
                rspec_node['sliver_id'] = sliver['node_id']
                rspec_node['client_id'] = node['hostname']
                rspec_node['slivers'] = [sliver]

                
            rspec_nodes.append(rspec_node)
        return rspec_nodes 

    def get_leases_and_channels(self, slice=None, options={}):
        
        slices = self.driver.shell.getSlices({}, [])
        nodes = self.driver.shell.getNodes({}, [])
        leases = self.driver.shell.getReservedNodes({}, [])
        channels = self.driver.shell.getChannels({}, [])
        reserved_channels = self.driver.shell.getReservedChannels()
        grain = self.driver.testbedInfo['grain']

        if slice:
            all_leases = []
            all_leases.extend(leases)
            all_reserved_channels = []
            all_reserved_channels.extend(reserved_channels)
            for lease in all_leases:
                 if lease['slice_id'] != slice['slice_id']:
                     leases.remove(lease)
            for channel in all_reserved_channels:
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
                     nodename = node['hostname']
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


    def get_channels(self, slice=None, options={}):
 
        all_channels = self.driver.shell.getChannels({}, [])
        channels = []
        if slice:
            reserved_channels = self.driver.shell.getReservedChannels()
            reserved_channel_ids = []
            for channel in reserved_channels:
                 if channel['slice_id'] == slice['slice_id']:
                     reserved_channel_ids.append(channel['channel_id'])

            for channel in all_channels:
                 if channel['channel_id'] in reserved_channel_ids:
                     channels.append(channel)
        else:
            channels = all_channels

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
           nodes = self.get_nodes(slice_xrn, slice, slivers, options)
           rspec.version.add_nodes(nodes)
           # add sliver defaults
           default_sliver = slivers.get(None, [])
           if default_sliver:
              default_sliver_attribs = default_sliver.get('tags', [])
              for attrib in default_sliver_attribs:
                  logger.info(attrib)
                  rspec.version.add_default_sliver_attribute(attrib['tagname'], attrib['value'])
           # add wifi channels
           channels = self.get_channels(slice, options)
           rspec.version.add_channels(channels)

        if not options.get('list_leases') or options.get('list_leases') and options['list_leases'] != 'resources':
           leases, channels = self.get_leases_and_channels(slice)
           rspec.version.add_leases(leases, channels)

        return rspec.toxml()


