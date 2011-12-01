
#!/usr/bin/python

# import modules used here -- sys is a very standard one
import sys
import httplib
import json


from sfa.rspecs.version_manager import VersionManager
from sfa.senslab.OARrestapi import *
from sfa.senslab.slabdriver import SlabDriver
from sfa.util.config import Config
from sfa.util.xrn import hrn_to_urn, urn_to_hrn, urn_to_sliver_id
from sfa.util.plxrn import PlXrn, hostname_to_urn, hrn_to_pl_slicename

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import Node
#from sfa.rspecs.elements.link import Link
#from sfa.rspecs.elements.sliver import Sliver
#from sfa.rspecs.elements.login import Login
#from sfa.rspecs.elements.location import Location
#from sfa.rspecs.elements.interface import Interface
#from sfa.rspecs.elements.services import Services
#from sfa.rspecs.elements.pltag import PLTag
from sfa.util.topology import Topology
from sfa.rspecs.version_manager import VersionManager
#from sfa.plc.vlink import get_tc_rate
from sfa.util.sfatime import epochparse


class OARrspec:

    
    sites = {}
    nodes = {}
    api = None
    interfaces = {}
    links = {}
    node_tags = {}
    
    prepared=False
    #panos new user options variable
    user_options = {}
    
    def __init__(self ,api):
    #def __init__(self ,api, user_options={}):
	self.OARImporter = OARapi()	
        self.driver = SlabDriver(Config())
	#self.user_options = user_options
	self.api = api 
	print >>sys.stderr,"\r\n \r\n \t\t_____________INIT OARRSPEC__ api : %s" %(api)

    def prepare_sites(self, force=False):
	print >>sys.stderr,'\r\n \r\n ++++++++++++++\t\t prepare_sites'
        if not self.sites or force:  
             for site in self.OARImporter.GetSites():
		print >>sys.stderr,'prepare_sites : site ', site		    
                self.sites[site['site_id']] = site
	
    
    def prepare_nodes(self, force=False):
        if not self.nodes or force:
            for node in self.driver.GetNodes():
            #for node in self.OARImporter.GetNodes():
                self.nodes[node['node_id']] = node
		
    #def prepare_interfaces(self, force=False):
        #if not self.interfaces or force:
            #for interface in self.api.plshell.GetInterfaces(self.api.plauth):
                #self.interfaces[interface['interface_id']] = interface

    #def prepare_node_tags(self, force=False):
        #if not self.node_tags or force:
            #for node_tag in self.api.plshell.GetNodeTags(self.api.plauth):
                #self.node_tags[node_tag['node_tag_id']] = node_tag
		
    def prepare_links(self, force=False):
        if not self.links or force:
            pass

    def prepare(self, force=False):
        if not self.prepared or force:
            #self.prepare_sites(force)
            self.prepare_nodes(force)
            
            #self.prepare_links(force)
            #self.prepare_interfaces(force)
            #self.prepare_node_tags(force)	    
            # add site/interface info to nodes
            for node_id in self.nodes:
                node = self.nodes[node_id]
                #site = self.sites[node['site_id']]
                #interfaces = [self.interfaces[interface_id] for interface_id in node['interface_ids']]
                #tags = [self.node_tags[tag_id] for tag_id in node['node_tag_ids']]
		node['network'] = self.driver.root_auth	
                node['network_urn'] = hrn_to_urn(node['network'], 'authority+am')
                #node['urn'] = hostname_to_urn(node['network'], node['site_login_base'], node['hostname'])
                node['site_urn'] = hrn_to_urn(PlXrn.site_hrn(node['network'], node['site_login_base']), 'authority+sa') 
                node['urn'] = hostname_to_urn(node['network'], node['site_login_base'], node['hostname'])
                #node['urn'] = PlXrn(auth=node['network']+'.',hostname=node['hostname']).get_urn()

                #node['site'] = site
                #node['interfaces'] = interfaces
                #node['tags'] = tags

        self.prepared = True 
        #print >>sys.stderr, "\r\n OARrspec  prepare node 10",self.nodes[10]  
	#print >>sys.stderr, " \r\n \t\t prepare prepare_nodes \r\n %s " %(self.nodes)
        
    def get_nodes(self):
        filtre = {}
        #tags_filter = {}
        #if slice and 'node_ids' in slice and slice['node_ids']:
            #filter['node_id'] = slice['node_ids']
            #tags_filter=filter.copy()
        
        #filter.update({'peer_id': None})
        nodes = self.driver.GetNodes(filtre)
        
        #site_ids = []
        interface_ids = []
        tag_ids = []
        nodes_dict = {}
        for node in nodes:
            #site_ids.append(node['site_id'])
            #interface_ids.extend(node['interface_ids'])
            #tag_ids.extend(node['node_tag_ids'])
            nodes_dict[node['node_id']] = node
    
        # get sites
        #sites_dict  = self.get_sites({'site_id': site_ids}) 
        # get interfaces
        #interfaces = self.get_interfaces({'interface_id':interface_ids}) 
        # get tags
        #node_tags = self.get_node_tags(tags_filter)
        # get initscripts
        #pl_initscripts = self.get_pl_initscripts()
        
        #links = self.get_links(sites_dict, nodes_dict, interfaces)
    
        rspec_nodes = []
        for node in nodes:
            # skip whitelisted nodes
            #if node['slice_ids_whitelist']:
                #if not slice or slice['slice_id'] not in node['slice_ids_whitelist']:
                    #continue
            rspec_node = Node()
            # xxx how to retrieve site['login_base']
            #site_id=node['site_id']
            #site=sites_dict[site_id]
            rspec_node['component_id'] = hostname_to_urn(self.driver.root_auth, node['site_login_base'], node['hostname'])
            rspec_node['component_name'] = node['hostname']
            rspec_node['component_manager_id'] = hrn_to_urn(self.driver.root_auth, 'authority+sa')
            rspec_node['authority_id'] = hrn_to_urn(PlXrn.site_hrn(self.driver.root_auth, node['site_login_base']), 'authority+sa')
            rspec_node['boot_state'] = node['boot_state']
            if node['posx'] and node['posy']:  
                location = Location({'longitude':node['posx'], 'latitude': node['posy']})
                rspec_node['location'] = location

            rspec_node['exclusive'] = 'True'
            rspec_node['hardware_types']= [HardwareType({'name': 'senslab sensor node'})]
            # only doing this because protogeni rspec needs
            # to advertise available initscripts 
            #rspec_node['pl_initscripts'] = pl_initscripts.values()
                # add site/interface info to nodes.
            # assumes that sites, interfaces and tags have already been prepared.
            #site = sites_dict[node['site_id']]
            #if site['longitude'] and site['latitude']:  
                #location = Location({'longitude': site['longitude'], 'latitude': site['latitude']})
                #rspec_node['location'] = location
            rspec_node['interfaces'] = []
            #if_count=0
            #for if_id in node['interface_ids']:
                #interface = Interface(interfaces[if_id]) 
                #interface['ipv4'] = interface['ip']
                #interface['component_id'] = PlXrn(auth=self.api.hrn, interface='node%s:eth%s' % (node['node_id'], if_count)).get_urn()
                #rspec_node['interfaces'].append(interface)
                #if_count+=1
    
            #tags = [PLTag(node_tags[tag_id]) for tag_id in node['node_tag_ids']]
            rspec_node['tags'] = []
            #if node['node_id'] in slivers:
                ## add sliver info
                #sliver = slivers[node['node_id']]
                #rspec_node['sliver_id'] = sliver['sliver_id']
                #rspec_node['client_id'] = node['hostname']
                #rspec_node['slivers'] = [sliver]
                
                ## slivers always provide the ssh service
                #login = Login({'authentication': 'ssh-keys', 'hostname': node['hostname'], 'port':'22'})
                #service = Services({'login': login})
                #rspec_node['services'] = [service]
            rspec_nodes.append(rspec_node)
        return (rspec_nodes)
        
#from plc/aggregate.py 
    def get_rspec(self, slice_xrn=None, version = None):
	print>>sys.stderr, " \r\n OARrspec \t\t get_rspec **************\r\n" 
        #self.prepare()
	
        rspec = None
	version_manager = VersionManager()
	version = version_manager.get_version(version)
        #rspec_version = RSpecVersion(version)
	#print >>sys.stderr, '\r\n \t\t rspec_version type',version_manager['type']
	
	if not slice_xrn:
            rspec_version = version_manager._get_version(version.type, version.version, 'ad')
        else:
            rspec_version = version_manager._get_version(version.type, version.version, 'manifest')
      
        rspec = RSpec(version=rspec_version, user_options=self.user_options)
        
        nodes = self.get_nodes()
        rspec.version.add_nodes(nodes)
      
	print >>sys.stderr, 'after add_nodes '
      

        return rspec.toxml()          
