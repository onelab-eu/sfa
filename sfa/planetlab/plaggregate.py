#!/usr/bin/python
from collections import defaultdict
from sfa.util.xrn import Xrn, hrn_to_urn, urn_to_hrn, get_authority, get_leaf
from sfa.util.sfatime import utcparse, datetime_to_string
from sfa.util.sfalogging import logger
from sfa.util.faults import SliverDoesNotExist
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

from sfa.planetlab.plxrn import PlXrn, hostname_to_urn, hrn_to_pl_slicename, slicename_to_hrn, top_auth, hash_loginbase
from sfa.planetlab.vlink import get_tc_rate
from sfa.planetlab.topology import Topology
from sfa.storage.model import SliverAllocation


import time

class PlAggregate:

    def __init__(self, driver):
        self.driver = driver

    def get_nodes(self, options=None):
        if options is None: options={}
        filter = {'peer_id': None}
        geni_available = options.get('geni_available')    
        if geni_available == True:
            filter['boot_state'] = 'boot'
        nodes = self.driver.shell.GetNodes(filter)
       
        return nodes  
 
    def get_sites(self, filter=None):
        if filter is None: filter={}
        sites = {}
        for site in self.driver.shell.GetSites(filter):
            sites[site['site_id']] = site
        return sites

    def get_interfaces(self, filter=None):
        if filter is None: filter={}
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

    def get_node_tags(self, filter=None):
        if filter is None: filter={}
        node_tags = {}
        for node_tag in self.driver.shell.GetNodeTags(filter):
            node_tags[node_tag['node_tag_id']] = node_tag
        return node_tags

    def get_pl_initscripts(self, filter=None):
        if filter is None: filter={}
        pl_initscripts = {}
        filter.update({'enabled': True})
        for initscript in self.driver.shell.GetInitScripts(filter):
            pl_initscripts[initscript['initscript_id']] = initscript
        return pl_initscripts

    def get_slivers(self, urns, options=None):
        if options is None: options={}
        names = set()
        slice_ids = set()
        node_ids = []
        slice_hrn = None
        for urn in urns:
            xrn = PlXrn(xrn=urn)
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
                slice_hrn = xrn.get_hrn()

        filter = {}
        filter['peer_id'] = None
        if slice_ids:
            filter['slice_id'] = list(slice_ids)
        # get all slices
        all_slices = self.driver.shell.GetSlices(filter, ['slice_id', 'name', 'hrn', 'person_ids', 'node_ids', 'slice_tag_ids', 'expires'])
        if slice_hrn:
            slices = [slice for slice in all_slices if slice['hrn'] == slice_hrn]
        else:
            slices = all_slices
      
        if not slices:
            return []
        slice = slices[0]     
        slice['hrn'] = slice_hrn   

        # get sliver users
        persons = []
        person_ids = []
        for slice in slices:
            person_ids.extend(slice['person_ids'])
        if person_ids:
            persons = self.driver.shell.GetPersons(person_ids)
                 
        # get user keys
        keys = {}
        key_ids = []
        for person in persons:
            key_ids.extend(person['key_ids'])
        
        if key_ids:
            key_list = self.driver.shell.GetKeys(key_ids)
            for key in key_list:
                keys[key['key_id']] = key  

        # construct user key info
        users = []
        for person in persons:
            person_urn = hrn_to_urn(self.driver.shell.GetPersonHrn(int(person['person_id'])), 'user')
            user = {
                'login': slice['name'], 
                'user_urn': person_urn,
                'keys': [keys[k_id]['key'] for k_id in person['key_ids'] if k_id in keys]
            }
            users.append(user)

        if node_ids:
            node_ids = [node_id for node_id in node_ids if node_id in slice['node_ids']]
            slice['node_ids'] = node_ids
        tags_dict = self.get_slice_tags(slice)
        nodes_dict = self.get_slice_nodes(slice, options)
        slivers = []
        for node in nodes_dict.values():
            node.update(slice) 
            node['tags'] = tags_dict[node['node_id']]
            sliver_hrn = '%s.%s-%s' % (self.driver.hrn, slice['slice_id'], node['node_id'])
            node['sliver_id'] = Xrn(sliver_hrn, type='sliver').urn
            node['urn'] = node['sliver_id'] 
            node['services_user'] = users
            slivers.append(node)
        return slivers

    def node_to_rspec_node(self, node, sites, interfaces, node_tags, pl_initscripts=None, grain=None, options=None):
        if pl_initscripts is None: pl_initscripts=[]
        if options is None: options={}
        rspec_node = NodeElement()
        # xxx how to retrieve site['login_base']
        site=sites[node['site_id']]
        rspec_node['component_id'] = hostname_to_urn(self.driver.hrn, site['login_base'], node['hostname'])
        rspec_node['component_name'] = node['hostname']
        rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
        rspec_node['authority_id'] = hrn_to_urn(PlXrn.site_hrn(self.driver.hrn, site['login_base']), 'authority+sa')
        # do not include boot state (<available> element) in the manifest rspec
        rspec_node['boot_state'] = node['boot_state']
        if node['boot_state'] == 'boot': 
            rspec_node['available'] = 'true'
        else:
            rspec_node['available'] = 'false'

        #distinguish between Shared and Reservable nodes
        if node['node_type'] == 'reservable':
            rspec_node['exclusive'] = 'true'
        else:
            rspec_node['exclusive'] = 'false'

        rspec_node['hardware_types'] = [HardwareType({'name': 'plab-pc'}),
                                        HardwareType({'name': 'pc'})]
        # only doing this because protogeni rspec needs
        # to advertise available initscripts
        rspec_node['pl_initscripts'] = pl_initscripts.values()
        # add site/interface info to nodes.
        # assumes that sites, interfaces and tags have already been prepared.
        if site['longitude'] and site['latitude']:
            location = Location({'longitude': site['longitude'], 'latitude': site['latitude'], 'country': 'unknown'})
            rspec_node['location'] = location
        # Granularity
        granularity = Granularity({'grain': grain})
        rspec_node['granularity'] = granularity
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
        tags = [PLTag(node_tags[tag_id]) for tag_id in node['node_tag_ids'] if tag_id in node_tags]
        rspec_node['tags'] = tags
        return rspec_node

    def sliver_to_rspec_node(self, sliver, sites, interfaces, node_tags, \
                             pl_initscripts, sliver_allocations):
        # get the granularity in second for the reservation system
        grain = self.driver.shell.GetLeaseGranularity()
        rspec_node = self.node_to_rspec_node(sliver, sites, interfaces, node_tags, pl_initscripts, grain)
        # xxx how to retrieve site['login_base']
        rspec_node['expires'] = datetime_to_string(utcparse(sliver['expires']))
        # remove interfaces from manifest
        rspec_node['interfaces'] = []
        # add sliver info
        rspec_sliver = Sliver({'sliver_id': sliver['urn'],
                         'name': sliver['name'],
                         'type': 'plab-vserver',
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
                       'username': sliver['name'],
                       'login': sliver['name']
                      })
        service = ServicesElement({'login': login,
                            'services_user': sliver['services_user']})
        rspec_node['services'] = [service]    
        return rspec_node      

    def get_slice_tags(self, slice):
        slice_tag_ids = []
        slice_tag_ids.extend(slice['slice_tag_ids'])
        tags = self.driver.shell.GetSliceTags({'slice_tag_id': slice_tag_ids})
        # sorted by node_id
        tags_dict = defaultdict(list)
        for tag in tags:
            tags_dict[tag['node_id']] = tag
        return tags_dict

    def get_slice_nodes(self, slice, options=None):
        if options is None: options={}
        nodes_dict = {}
        filter = {'peer_id': None}
        tags_filter = {}
        if slice and slice.get('node_ids'):
            filter['node_id'] = slice['node_ids']
        else:
            # there are no nodes to look up
            return nodes_dict
        tags_filter=filter.copy()
        geni_available = options.get('geni_available')
        if geni_available == True:
            filter['boot_state'] = 'boot'
        nodes = self.driver.shell.GetNodes(filter)
        for node in nodes:
            nodes_dict[node['node_id']] = node
        return nodes_dict

    def rspec_node_to_geni_sliver(self, rspec_node, sliver_allocations=None):
        if sliver_allocations is None: sliver_allocations={}
        if rspec_node['sliver_id'] in sliver_allocations:
            # set sliver allocation and operational status
            sliver_allocation = sliver_allocations[rspec_node['sliver_id']]
            if sliver_allocation:
                allocation_status = sliver_allocation.allocation_state
                if allocation_status == 'geni_allocated':
                    op_status =  'geni_pending_allocation'
                elif allocation_status == 'geni_provisioned':
                    if rspec_node['boot_state'] == 'boot':
                        op_status = 'geni_ready'
                    else:
                        op_status = 'geni_failed'
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

    def get_leases(self, slice=None, options=None):
        if options is None: options={}
        
        now = int(time.time())
        filter={}
        filter.update({'clip':now})
        if slice:
           filter.update({'name':slice['name']})
        return_fields = ['lease_id', 'hostname', 'site_id', 'name', 't_from', 't_until']
        leases = self.driver.shell.GetLeases(filter)
        grain = self.driver.shell.GetLeaseGranularity()

        site_ids = []
        for lease in leases:
            site_ids.append(lease['site_id'])

        # get sites
        sites_dict  = self.get_sites({'site_id': site_ids}) 
  
        rspec_leases = []
        for lease in leases:

            rspec_lease = Lease()
            
            # xxx how to retrieve site['login_base']
            site_id=lease['site_id']
            site=sites_dict[site_id]

            rspec_lease['component_id'] = hrn_to_urn(self.driver.shell.GetNodeHrn(lease['hostname']), 'node')
            slice_hrn = self.driver.shell.GetSliceHrn(lease['slice_id'])
            slice_urn = hrn_to_urn(slice_hrn, 'slice')
            rspec_lease['slice_id'] = slice_urn
            rspec_lease['start_time'] = lease['t_from']
            rspec_lease['duration'] = (lease['t_until'] - lease['t_from']) / grain
            rspec_leases.append(rspec_lease)
        return rspec_leases

    
    def list_resources(self, version = None, options=None):
        if options is None: options={}

        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type, version.version, 'ad')
        rspec = RSpec(version=rspec_version, user_options=options)
       
        if not options.get('list_leases') or options['list_leases'] != 'leases':
            # get nodes
            nodes  = self.get_nodes(options)
            site_ids = []
            interface_ids = []
            tag_ids = []
            nodes_dict = {}
            for node in nodes:
                site_ids.append(node['site_id'])
                interface_ids.extend(node['interface_ids'])
                tag_ids.extend(node['node_tag_ids'])
                nodes_dict[node['node_id']] = node
            sites = self.get_sites({'site_id': site_ids})
            interfaces = self.get_interfaces({'interface_id':interface_ids})
            node_tags = self.get_node_tags({'node_tag_id': tag_ids})
            pl_initscripts = self.get_pl_initscripts()
            # convert nodes to rspec nodes
            rspec_nodes = []
            for node in nodes:
                rspec_node = self.node_to_rspec_node(node, sites, interfaces, node_tags, pl_initscripts)
                rspec_nodes.append(rspec_node)
            rspec.version.add_nodes(rspec_nodes)

            # add links
            links = self.get_links(sites, nodes_dict, interfaces)        
            rspec.version.add_links(links)

        if not options.get('list_leases') or options.get('list_leases') and options['list_leases'] != 'resources':
           leases = self.get_leases()
           rspec.version.add_leases(leases)

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
      
        if not options.get('list_leases') or options['list_leases'] != 'leases':
            # add slivers
            site_ids = []
            interface_ids = []
            tag_ids = []
            nodes_dict = {}
            for sliver in slivers:
                site_ids.append(sliver['site_id'])
                interface_ids.extend(sliver['interface_ids'])
                tag_ids.extend(sliver['node_tag_ids'])
                nodes_dict[sliver['node_id']] = sliver
            sites = self.get_sites({'site_id': site_ids})
            interfaces = self.get_interfaces({'interface_id':interface_ids})
            node_tags = self.get_node_tags({'node_tag_id': tag_ids})
            pl_initscripts = self.get_pl_initscripts()
            rspec_nodes = []
            for sliver in slivers:
                if sliver['slice_ids_whitelist'] and sliver['slice_id'] not in sliver['slice_ids_whitelist']:
                    continue
                rspec_node = self.sliver_to_rspec_node(sliver, sites, interfaces, node_tags, 
                                                       pl_initscripts, sliver_allocation_dict)
                # manifest node element shouldn't contain available attribute
                rspec_node.pop('available')
                rspec_nodes.append(rspec_node) 
                geni_sliver = self.rspec_node_to_geni_sliver(rspec_node, sliver_allocation_dict)
                geni_slivers.append(geni_sliver)
            rspec.version.add_nodes(rspec_nodes)

            # add sliver defaults
            #default_sliver = slivers.get(None, [])
            #if default_sliver:
            #    default_sliver_attribs = default_sliver.get('tags', [])
            #    for attrib in default_sliver_attribs:
            #        rspec.version.add_default_sliver_attribute(attrib['tagname'], attrib['value'])

            # add links 
            links = self.get_links(sites, nodes_dict, interfaces)        
            rspec.version.add_links(links)

        if not options.get('list_leases') or options['list_leases'] != 'resources':
            if slivers:
                leases = self.get_leases(slivers[0])
                rspec.version.add_leases(leases)

               
        return {'geni_urn': geni_urn, 
                'geni_rspec': rspec.toxml(),
                'geni_slivers': geni_slivers}
