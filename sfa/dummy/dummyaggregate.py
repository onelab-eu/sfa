#!/usr/bin/python
from sfa.util.xrn import Xrn, hrn_to_urn, urn_to_hrn
from sfa.util.sfatime import utcparse, datetime_to_string
from sfa.util.sfalogging import logger

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import NodeElement
from sfa.rspecs.elements.link import Link
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.elements.services import ServicesElement
from sfa.rspecs.elements.pltag import PLTag
from sfa.rspecs.elements.lease import Lease
from sfa.rspecs.elements.granularity import Granularity
from sfa.rspecs.version_manager import VersionManager

from sfa.dummy.dummyxrn import DummyXrn, hostname_to_urn, hrn_to_dummy_slicename, slicename_to_hrn

import time

class DummyAggregate:

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
        slice_name = hrn_to_dummy_slicename(slice_hrn)
        slices = self.driver.shell.GetSlices({'slice_name': slice_name})
        if not slices:
            return (slice, slivers)
        slice = slices[0]
        
        # sort slivers by node id 
        slice_nodes = []
        if 'node_ids' in slice.keys():
            slice_nodes = self.driver.shell.GetNodes({'node_ids': slice['node_ids']}) 
        for node in slice_nodes:
            slivers[node['node_id']] = node  

        return (slice, slivers)

    def get_nodes(self, slice_xrn, slice=None,slivers=[], options={}):
        # if we are dealing with a slice that has no node just return 
        # and empty list    
        if slice_xrn:
            if not slice or 'node_ids' not in slice.keys() or not slice['node_ids']:
                return []

        filter = {}
        if slice and 'node_ids' in slice and slice['node_ids']:
            filter['node_ids'] = slice['node_ids']

        nodes = self.driver.shell.GetNodes(filter)
        
        rspec_nodes = []
        for node in nodes:
            rspec_node = NodeElement()
            # xxx how to retrieve site['login_base']
            site=self.driver.testbedInfo
            rspec_node['component_id'] = hostname_to_urn(self.driver.hrn, site['name'], node['hostname'])
            rspec_node['component_name'] = node['hostname']
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
            rspec_node['authority_id'] = hrn_to_urn(DummyXrn.site_hrn(self.driver.hrn, site['name']), 'authority+sa')
            rspec_node['exclusive'] = 'false'
            rspec_node['hardware_types'] = [HardwareType({'name': 'plab-pc'}),
                                            HardwareType({'name': 'pc'})]
             # add site/interface info to nodes.
            # assumes that sites, interfaces and tags have already been prepared.
            if site['longitude'] and site['latitude']:  
                location = Location({'longitude': site['longitude'], 'latitude': site['latitude'], 'country': 'unknown'})
                rspec_node['location'] = location

            if node['node_id'] in slivers:
                # add sliver info
                sliver = slivers[node['node_id']]
                rspec_node['client_id'] = node['hostname']
                rspec_node['slivers'] = [sliver]
                
                # slivers always provide the ssh service
                login = Login({'authentication': 'ssh-keys', 'hostname': node['hostname'], 'port':'22', 'username': slice['slice_name']})
                service = ServicesElement({'login': login})
                rspec_node['services'] = [service]
            rspec_nodes.append(rspec_node)
        return rspec_nodes
             

    
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

        nodes = self.get_nodes(slice_xrn, slice, slivers, options)
        rspec.version.add_nodes(nodes)
        # add sliver defaults
        default_sliver = slivers.get(None, [])
        if default_sliver:
            default_sliver_attribs = default_sliver.get('tags', [])
            for attrib in default_sliver_attribs:
                 logger.info(attrib)
                 rspec.version.add_default_sliver_attribute(attrib['tagname'], attrib['value'])
        
        return rspec.toxml()


