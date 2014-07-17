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

from sfa.storage.model import SliverAllocation
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

    def get_nodes(self, options=None):
        if options is None: options={}
        filter = {}
        nodes = self.driver.shell.GetNodes(filter)
        return nodes

    def get_slivers(self, urns, options=None):
        if options is None: options={}
        slice_names = set()
        slice_ids = set()
        node_ids = []
        for urn in urns:
            xrn = DummyXrn(xrn=urn)
            if xrn.type == 'sliver':
                 # id: slice_id-node_id
                try:
                    sliver_id_parts = xrn.get_sliver_id_parts()
                    slice_id = int(sliver_id_parts[0])
                    node_id = int(sliver_id_parts[1])
                    slice_ids.add(slice_id)
                    node_ids.append(node_id)
                except ValueError:
                    pass
            else:
                slice_names.add(xrn.dummy_slicename())

        filter = {}
        if slice_names:
            filter['slice_name'] = list(slice_names)
        if slice_ids:
            filter['slice_id'] = list(slice_ids)
        # get slices
        slices = self.driver.shell.GetSlices(filter)
        if not slices:
            return []
        slice = slices[0]
        slice['hrn'] = DummyXrn(auth=self.driver.hrn, slicename=slice['slice_name']).hrn

        # get sliver users
        users = []
        user_ids = []
        for slice in slices:
            if 'user_ids' in slice.keys():
                user_ids.extend(slice['user_ids'])
        if user_ids:
            users = self.driver.shell.GetUsers({'user_ids': user_ids})

        # construct user key info
        users_list = []
        for user in users:
            name = user['email'][0:user['email'].index('@')]
            user = {
                'login': slice['slice_name'],
                'user_urn': Xrn('%s.%s' % (self.driver.hrn, name), type='user').urn,
                'keys': user['keys']
            }
            users_list.append(user)

        if node_ids:
            node_ids = [node_id for node_id in node_ids if node_id in slice['node_ids']]
            slice['node_ids'] = node_ids
        nodes_dict = self.get_slice_nodes(slice, options)
        slivers = []
        for node in nodes_dict.values():
            node.update(slice)
            sliver_hrn = '%s.%s-%s' % (self.driver.hrn, slice['slice_id'], node['node_id'])
            node['sliver_id'] = Xrn(sliver_hrn, type='sliver').urn
            node['urn'] = node['sliver_id']
            node['services_user'] = users
            slivers.append(node)
        return slivers

    def node_to_rspec_node(self, node, options=None):
        if options is None: options={}
        rspec_node = NodeElement()
        site=self.driver.testbedInfo
        rspec_node['component_id'] = hostname_to_urn(self.driver.hrn, site['name'], node['hostname'])
        rspec_node['component_name'] = node['hostname']
        rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
        rspec_node['authority_id'] = hrn_to_urn(DummyXrn.site_hrn(self.driver.hrn, site['name']), 'authority+sa')
        #distinguish between Shared and Reservable nodes
        rspec_node['exclusive'] = 'false'

        rspec_node['hardware_types'] = [HardwareType({'name': 'dummy-pc'}),
                                        HardwareType({'name': 'pc'})]
        if site['longitude'] and site['latitude']:
            location = Location({'longitude': site['longitude'], 'latitude': site['latitude'], 'country': 'unknown'})
            rspec_node['location'] = location
        return rspec_node

    def sliver_to_rspec_node(self, sliver, sliver_allocations):
        rspec_node = self.node_to_rspec_node(sliver)
        rspec_node['expires'] = datetime_to_string(utcparse(sliver['expires']))
        # add sliver info
        rspec_sliver = Sliver({'sliver_id': sliver['urn'],
                         'name': sliver['slice_name'],
                         'type': 'dummy-vserver',
                         'tags': []})
        rspec_node['sliver_id'] = rspec_sliver['sliver_id']
        if sliver['urn'] in sliver_allocations:
            rspec_node['client_id'] = sliver_allocations[sliver['urn']].client_id
            if sliver_allocations[sliver['urn']].component_id:
                rspec_node['component_id'] = sliver_allocations[sliver['urn']].component_id
        rspec_node['slivers'] = [rspec_sliver]

        # slivers always provide the ssh service
        login = Login({'authentication': 'ssh-keys',
                       'hostname': sliver['hostname'],
                       'port':'22',
                       'username': sliver['slice_name'],
                       'login': sliver['slice_name']
                      })
        return rspec_node

    def get_slice_nodes(self, slice, options=None):
        if options is None: options={}
        nodes_dict = {}
        filter = {}
        if slice and slice.get('node_ids'):
            filter['node_ids'] = slice['node_ids']
        else:
            # there are no nodes to look up
            return nodes_dict
        nodes = self.driver.shell.GetNodes(filter)
        for node in nodes:
            nodes_dict[node['node_id']] = node
        return nodes_dict

    def rspec_node_to_geni_sliver(self, rspec_node, sliver_allocations = None):
        if sliver_allocations is None: sliver_allocations={}
        if rspec_node['sliver_id'] in sliver_allocations:
            # set sliver allocation and operational status
            sliver_allocation = sliver_allocations[rspec_node['sliver_id']]
            if sliver_allocation:
                allocation_status = sliver_allocation.allocation_state
                if allocation_status == 'geni_allocated':
                    op_status =  'geni_pending_allocation'
                elif allocation_status == 'geni_provisioned':
                    op_status = 'geni_ready'
                else:
                    op_status = 'geni_unknown'
            else:
                allocation_status = 'geni_unallocated'
        else:
            allocation_status = 'geni_unallocated'
            op_status = 'geni_failed'
        # required fields
        geni_sliver = {'geni_sliver_urn': rspec_node['sliver_id'],
                       'geni_expires': rspec_node['expires'],
                       'geni_allocation_status' : allocation_status,
                       'geni_operational_status': op_status,
                       'geni_error': '',
                       }
        return geni_sliver

    def list_resources(self, version = None, options=None):
        if options is None: options={}

        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type, version.version, 'ad')
        rspec = RSpec(version=rspec_version, user_options=options)

        # get nodes
        nodes  = self.get_nodes(options)
        nodes_dict = {}
        for node in nodes:
            nodes_dict[node['node_id']] = node

        # convert nodes to rspec nodes
        rspec_nodes = []
        for node in nodes:
            rspec_node = self.node_to_rspec_node(node)
            rspec_nodes.append(rspec_node)
        rspec.version.add_nodes(rspec_nodes)

        return rspec.toxml()

    def describe(self, urns, version=None, options=None):
        if options is None: options={}
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type, version.version, 'manifest')
        rspec = RSpec(version=rspec_version, user_options=options)

        # get slivers
        geni_slivers = []
        slivers = self.get_slivers(urns, options)
        if slivers:
            rspec_expires = datetime_to_string(utcparse(slivers[0]['expires']))
        else:
            rspec_expires = datetime_to_string(utcparse(time.time()))
        rspec.xml.set('expires',  rspec_expires)

        # lookup the sliver allocations
        geni_urn = urns[0]
        sliver_ids = [sliver['sliver_id'] for sliver in slivers]
        constraint = SliverAllocation.sliver_id.in_(sliver_ids)
        sliver_allocations = self.driver.api.dbsession().query(SliverAllocation).filter(constraint)
        sliver_allocation_dict = {}
        for sliver_allocation in sliver_allocations:
            geni_urn = sliver_allocation.slice_urn
            sliver_allocation_dict[sliver_allocation.sliver_id] = sliver_allocation

        # add slivers
        nodes_dict = {}
        for sliver in slivers:
            nodes_dict[sliver['node_id']] = sliver
        rspec_nodes = []
        for sliver in slivers:
            rspec_node = self.sliver_to_rspec_node(sliver, sliver_allocation_dict)
            rspec_nodes.append(rspec_node)
            geni_sliver = self.rspec_node_to_geni_sliver(rspec_node, sliver_allocation_dict)
            geni_slivers.append(geni_sliver)
        rspec.version.add_nodes(rspec_nodes)

        return {'geni_urn': geni_urn,
                'geni_rspec': rspec.toxml(),
                'geni_slivers': geni_slivers}

