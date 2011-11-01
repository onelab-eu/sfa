#!/usr/bin/python
from sfa.util.xrn import hrn_to_urn, urn_to_hrn
from sfa.util.plxrn import PlXrn, hostname_to_urn, hrn_to_pl_slicename

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.link import Link
from sfa.rspecs.elements.interface import Interface

from sfa.managers.vini.topology import PhysicalLinks
from sfa.rspecs.version_manager import VersionManager
from sfa.plc.vlink import get_tc_rate

class Aggregate:

    api = None
    sites = {}
    nodes = {}
    interfaces = {}
    links = {}
    node_tags = {}
    pl_initscripts = {} 
    prepared=False
    #panos new user options variable
    user_options = {}

    def __init__(self, api, user_options={}):
        self.api = api
        self.user_options = user_options

    def prepare_sites(self, filter={}, force=False):
        if not self.sites or force:  
            for site in self.api.driver.GetSites(filter):
                self.sites[site['site_id']] = site
    
    def prepare_nodes(self, filter={}, force=False):
        if not self.nodes or force:
            filter.update({'peer_id': None})
            nodes = self.api.driver.GetNodes(filter)
            site_ids = []
            interface_ids = []
            tag_ids = []
            for node in nodes:
                site_ids.append(node['site_id'])
                interface_ids.extend(node['interface_ids'])
                tag_ids.extend(node['node_tag_ids'])
            self.prepare_sites({'site_id': site_ids})
            self.prepare_interfaces({'interface_id': interface_ids})
            self.prepare_node_tags({'node_tag_id': tag_ids}) 
            for node in nodes:
                # add site/interface info to nodes.
                # assumes that sites, interfaces and tags have already been prepared.
                site = self.sites[node['site_id']]
                interfaces = [self.interfaces[interface_id] for interface_id in node['interface_ids']]
                tags = [self.node_tags[tag_id] for tag_id in node['node_tag_ids']]
                node['network'] = self.api.hrn
                node['network_urn'] = hrn_to_urn(self.api.hrn, 'authority+am')
                node['urn'] = hostname_to_urn(self.api.hrn, site['login_base'], node['hostname'])
                node['site_urn'] = hrn_to_urn(PlXrn.site_hrn(self.api.hrn, site['login_base']), 'authority+sa')
                node['site'] = site
                node['interfaces'] = interfaces
                node['tags'] = tags
                self.nodes[node['node_id']] = node

    def prepare_interfaces(self, filter={}, force=False):
        if not self.interfaces or force:
            for interface in self.api.driver.GetInterfaces(filter):
                self.interfaces[interface['interface_id']] = interface

    def prepare_links(self, filter={}, force=False):
        # we're aobut to deprecate sfa_aggregate_type, need to get this right 
        # with the generic framework
        if not self.links or force:
            if not self.api.config.SFA_AGGREGATE_TYPE.lower() == 'vini':
                return

            for (site_id1, site_id2) in PhysicalLinks:
                link = Link()
                if not site_id1 in self.sites or site_id2 not in self.sites:
                    continue
                site1 = self.sites[site_id1]
                site2 = self.sites[site_id2]
                # get hrns
                site1_hrn = self.api.hrn + '.' + site1['login_base']
                site2_hrn = self.api.hrn + '.' + site2['login_base']
                # get the first node
                node1 = self.nodes[site1['node_ids'][0]]
                node2 = self.nodes[site2['node_ids'][0]]

                # set interfaces
                # just get first interface of the first node
                if1_xrn = PlXrn(auth=self.api.hrn, interface='node%s:eth0' % (node1['node_id']))
                if1_ipv4 = self.interfaces[node1['interface_ids'][0]]['ip']
                if2_xrn = PlXrn(auth=self.api.hrn, interface='node%s:eth0' % (node2['node_id']))
                if2_ipv4 = self.interfaces[node2['interface_ids'][0]]['ip']

                if1 = Interface({'component_id': if1_xrn.urn, 'ipv4': if1_ipv4} )
                if2 = Interface({'component_id': if2_xrn.urn, 'ipv4': if2_ipv4} )

                # set link
                link = Link({'capacity': '1000000', 'latency': '0', 'packet_loss': '0', 'type': 'ipv4'})
                link['interface1'] = if1
                link['interface2'] = if2
                link['component_name'] = "%s:%s" % (site1['login_base'], site2['login_base'])
                link['component_id'] = PlXrn(auth=self.api.hrn, interface=link['component_name']).get_urn()
                link['component_manager_id'] =  hrn_to_urn(self.api.hrn, 'authority+am')
                self.links[link['component_name']] = link


    def prepare_node_tags(self, filter={}, force=False):
        if not self.node_tags or force:
            for node_tag in self.api.driver.GetNodeTags(filter):
                self.node_tags[node_tag['node_tag_id']] = node_tag

    def prepare_pl_initscripts(self, filter={}, force=False):
        if not self.pl_initscripts or force:
            filter.update({'enabled': True})
            for initscript in self.api.driver.GetInitScripts(filter):
                self.pl_initscripts[initscript['initscript_id']] = initscript

    def prepare(self, slice = None, force=False):
        if not self.prepared or force or slice:
            if not slice:
                self.prepare_sites(force=force)
                self.prepare_interfaces(force=force)
                self.prepare_node_tags(force=force)
                self.prepare_nodes(force=force)
                self.prepare_links(force=force)
                self.prepare_pl_initscripts(force=force)
            else:
                self.prepare_sites({'site_id': slice['site_id']})
                self.prepare_interfaces({'node_id': slice['node_ids']})
                self.prepare_node_tags({'node_id': slice['node_ids']})
                self.prepare_nodes({'node_id': slice['node_ids']})
                self.prepare_links({'slice_id': slice['slice_id']})
                self.prepare_pl_initscripts()
            self.prepared = True  

    def get_rspec(self, slice_xrn=None, version = None):
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        if not slice_xrn:
            rspec_version = version_manager._get_version(version.type, version.version, 'ad')
        else:
            rspec_version = version_manager._get_version(version.type, version.version, 'manifest')
               
        rspec = RSpec(version=rspec_version, user_options=self.user_options)
        # get slice details if specified
        slice = None
        if slice_xrn:
            slice_hrn, _ = urn_to_hrn(slice_xrn)
            slice_name = hrn_to_pl_slicename(slice_hrn)
            slices = self.api.driver.GetSlices(slice_name)
            if slices:
                slice = slices[0]
            self.prepare(slice=slice)
        else:
            self.prepare()
            
        # filter out nodes with a whitelist:
        valid_nodes = [] 
        for node in self.nodes.values():
            # only doing this because protogeni rspec needs
            # to advertise available initscripts 
            node['pl_initscripts'] = self.pl_initscripts

            if slice and node['node_id'] in slice['node_ids']:
                valid_nodes.append(node)
            elif slice and slice['slice_id'] in node['slice_ids_whitelist']:
                valid_nodes.append(node)
            elif not slice and not node['slice_ids_whitelist']:
                valid_nodes.append(node)
    
        rspec.version.add_nodes(valid_nodes)
        rspec.version.add_interfaces(self.interfaces.values()) 
        rspec.version.add_links(self.links.values())

        # add slivers
        if slice_xrn and slice:
            slivers = []
            tags = self.api.driver.GetSliceTags(slice['slice_tag_ids'])

            # add default tags
            for tag in tags:
                # if tag isn't bound to a node then it applies to all slivers
                # and belongs in the <sliver_defaults> tag
                if not tag['node_id']:
                    rspec.version.add_default_sliver_attribute(tag['tagname'], tag['value'], self.api.hrn)
                if tag['tagname'] == 'topo_rspec' and tag['node_id']:
                    node = self.nodes[tag['node_id']]
                    value = eval(tag['value'])
                    for (id, realip, bw, lvip, rvip, vnet) in value:
                        bps = get_tc_rate(bw)
                        remote = self.nodes[id]
                        site1 = self.sites[node['site_id']]
                        site2 = self.sites[remote['site_id']]
                        link1_name = '%s:%s' % (site1['login_base'], site2['login_base']) 
                        link2_name = '%s:%s' % (site2['login_base'], site1['login_base']) 
                        p_link = None
                        if link1_name in self.links:
                            link = self.links[link1_name] 
                        elif link2_name in self.links:
                            link = self.links[link2_name]
                        v_link = Link()
                        
                        link.capacity = bps 
            for node_id in slice['node_ids']:
                try:
                    sliver = {}
                    sliver['hostname'] = self.nodes[node_id]['hostname']
                    sliver['node_id'] = node_id
                    sliver['slice_id'] = slice['slice_id']    
                    sliver['tags'] = []
                    slivers.append(sliver)

                    # add tags for this node only
                    for tag in tags:
                        if tag['node_id'] and (tag['node_id'] == node_id):
                            sliver['tags'].append(tag)
                except:
                    self.api.logger.log_exc('unable to add sliver %s to node %s' % (slice['name'], node_id))
            rspec.version.add_slivers(slivers, sliver_urn=slice_xrn)

        return rspec.toxml()
