
#!/usr/bin/python

# import modules used here -- sys is a very standard one
import sys
import httplib
import json


from sfa.rspecs.version_manager import VersionManager
from sfa.senslab.OARrestapi import *
#from sfa.senslab.slabdriver import SlabDriver
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

def hostname_to_hrn(root_auth,login_base,hostname):
    return PlXrn(auth=root_auth,hostname=login_base+'_'+hostname).get_hrn()

class SlabAggregate:

    
    sites = {}
    nodes = {}
    api = None
    interfaces = {}
    links = {}
    node_tags = {}
    
    prepared=False

    user_options = {}
    
    def __init__(self ,driver):
	self.OARImporter = OARapi()	
        self.driver = driver
	#self.api = api 
	print >>sys.stderr,"\r\n \r\n \t\t_____________INIT Slabaggregate api : %s" %(driver)


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
        slice_name = slice_hrn
        slices = self.driver.GetSlices(slice_name)
        if not slices:
            return (slice, slivers)
        slice = slices[0]

        # sort slivers by node id    
        for node_id in slice['node_ids']:
            sliver = Sliver({'sliver_id': urn_to_sliver_id(slice_urn, slice['slice_id'], node_id),
                             'name': slice['hrn'],
                             'type': 'slab-vm', 
                             'tags': []})
            slivers[node_id]= sliver

        # sort sliver attributes by node id    
        #tags = self.driver.GetSliceTags({'slice_tag_id': slice['slice_tag_ids']})
        #for tag in tags:
            ## most likely a default/global sliver attribute (node_id == None)
            #if tag['node_id'] not in slivers:
                #sliver = Sliver({'sliver_id': urn_to_sliver_id(slice_urn, slice['slice_id'], ""),
                                 #'name': 'slab-vm',
                                 #'tags': []})
                #slivers[tag['node_id']] = sliver
            #slivers[tag['node_id']]['tags'].append(tag)
        
        return (slice, slivers)
            
            
  
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
            node['hostname'] = hostname_to_hrn( self.driver.root_auth,node['site_login_base'], node['hostname'])
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
    def get_rspec(self, slice_xrn=None, version = None, options={}):
	print>>sys.stderr, " \r\n SlabAggregate \t\t get_rspec **************\r\n" 
      
	
        rspec = None
	version_manager = VersionManager()
	version = version_manager.get_version(version)
     
	
	if not slice_xrn:
            rspec_version = version_manager._get_version(version.type, version.version, 'ad')
        else:
            rspec_version = version_manager._get_version(version.type, version.version, 'manifest')
        #slice, slivers = self.get_slice_and_slivers(slice_xrn)
        rspec = RSpec(version=rspec_version, user_options=options)
        #if slice and 'expires' in slice:
           #rspec.xml.set('expires',  epochparse(slice['expires']))
         # add sliver defaults
        #nodes, links = self.get_nodes_and_links(slice, slivers)
        nodes = self.get_nodes() 
        rspec.version.add_nodes(nodes)

        #rspec.version.add_links(links)
        #default_sliver = slivers.get(None, [])
        #if default_sliver:
            #default_sliver_attribs = default_sliver.get('tags', [])
            #for attrib in default_sliver_attribs:
                #logger.info(attrib)
                #rspec.version.add_default_sliver_attribute(attrib['tagname'], attrib['value'])   

        return rspec.toxml()          
