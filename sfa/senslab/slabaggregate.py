# import modules used here -- sys is a very standard one
import sys
import httplib
import json



#from sfa.senslab.OARrestapi import *

from sfa.util.config import Config
from sfa.util.xrn import hrn_to_urn, urn_to_hrn, urn_to_sliver_id
from sfa.planetlab.plxrn import PlXrn, hostname_to_urn, hrn_to_pl_slicename

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import Node
#from sfa.rspecs.elements.login import Login
#from sfa.rspecs.elements.services import Services
from sfa.rspecs.elements.sliver import Sliver

from sfa.rspecs.version_manager import VersionManager

from sfa.util.sfatime import datetime_to_epoch

def hostname_to_hrn(root_auth,login_base,hostname):
    return PlXrn(auth=root_auth,hostname=login_base + '_'+hostname).get_hrn()

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
        slice_name = slice_hrn
        print >>sys.stderr,"\r\n \r\n \t\t_____________ Slabaggregate api get_slice_and_slivers "
        slices = self.driver.GetSlices(slice_filter= str(slice_name), slice_filter_type = 'slice_hrn')
        print >>sys.stderr,"\r\n \r\n \t\t_____________ Slabaggregate api get_slice_and_slivers  slices %s " %(slices)
        if not slices:
            return (slice, slivers)
        if isinstance(slice, list):
            slice = slices[0]
        else:
           slice =slices

        # sort slivers by node id , if there is a job
        #and therfore, node allocated to this slice
        if slice['oar_job_id'] is not -1:
            try:
                
                for node_id in slice['node_ids']:
                    #node_id = self.driver.root_auth + '.' + node_id
                    sliver = Sliver({'sliver_id': urn_to_sliver_id(slice_urn, slice['record_id_slice'], node_id),
                                    'name': slice['slice_hrn'],
                                    'type': 'slab-node', 
                                    'tags': []})
                    slivers[node_id]= sliver
            except KeyError:
                    print>>sys.stderr, " \r\n \t\t get_slice_and_slivers KeyError "
        ## sort sliver attributes by node id    
        ##tags = self.driver.GetSliceTags({'slice_tag_id': slice['slice_tag_ids']})
        ##for tag in tags:
            ### most likely a default/global sliver attribute (node_id == None)
            ##if tag['node_id'] not in slivers:
                ##sliver = Sliver({'sliver_id': urn_to_sliver_id(slice_urn, slice['slice_id'], ""),
                                 ##'name': 'slab-vm',
                                 ##'tags': []})
                ##slivers[tag['node_id']] = sliver
            ##slivers[tag['node_id']]['tags'].append(tag)
        print >>sys.stderr,"\r\n \r\n \t\t_____________ Slabaggregate api get_slice_and_slivers  slivers %s " %(slivers)
        return (slice, slivers)
            

        
    def get_nodes(self, slice=None,slivers=[], options={}):
        # NT: the semantic of this function is not clear to me :
        # if slice is not defined, then all the nodes should be returned
        # if slice is defined, we should return only the nodes that are part of this slice
        # but what is the role of the slivers parameter ?
        # So i assume that slice['node_ids'] will be the same as slivers for us
        filter = {}
        tags_filter = {}
        
        # Commenting this part since all nodes should be returned, even if a slice is provided
        #if slice :
        #    if 'node_ids' in slice and slice['node_ids']:
        #        #first case, a non empty slice was provided
        #        filter['hostname'] = slice['node_ids']
        #        tags_filter=filter.copy()
        #        nodes = self.driver.GetNodes(filter['hostname'])
        #    else :
        #        #second case, a slice was provided, but is empty
        #        nodes={}
        #else :
        #    #third case, no slice was provided
        #    nodes = self.driver.GetNodes()
        nodes = self.driver.GetNodes()
        #geni_available = options.get('geni_available')    
        #if geni_available:
            #filter['boot_state'] = 'boot'     
       
        #filter.update({'peer_id': None})
        #nodes = self.driver.GetNodes(filter['hostname'])
        
        #site_ids = []
        #interface_ids = []
        #tag_ids = []
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
       

        reserved_nodes=self.driver.GetReservedNodes()
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
            rspec_node['component_id'] = hostname_to_urn(self.driver.root_auth, node['site'], node['hostname'])
            rspec_node['component_name'] = node['hostname']  
            rspec_node['component_manager_id'] = hrn_to_urn(self.driver.root_auth, 'authority+sa')
            #rspec_node['component_manager_id'] = Xrn(self.driver.root_auth, 'authority+sa').get_urn()
            rspec_node['authority_id'] = hrn_to_urn(PlXrn.site_hrn(self.driver.root_auth, node['site']), 'authority+sa')
            # do not include boot state (<available> element) in the manifest rspec
            
            #if not slice:
            #    rspec_node['boot_state'] = node['boot_state']
            #    if node['hostname'] in reserved_nodes:
            #        rspec_node['boot_state'] = "Reserved"
            rspec_node['boot_state'] = node['boot_state']
            if node['hostname'] in reserved_nodes:
                rspec_node['boot_state'] = "Reserved"
            rspec_node['exclusive'] = 'True'
            rspec_node['hardware_types'] = [HardwareType({'name': 'slab-node'})]

            # only doing this because protogeni rspec needs
            # to advertise available initscripts 
            #rspec_node['pl_initscripts'] = None
            # add site/interface info to nodes.
            # assumes that sites, interfaces and tags have already been prepared.
            #site = sites_dict[node['site_id']]
         
            try:
                if node['posx'] and node['posy']:  
                    location = Location({'longitude':node['posx'], 'latitude': node['posy']})
                    rspec_node['location'] = location
            except KeyError:
                    pass
            #rspec_node['interfaces'] = []
            #if_count=0
            #for if_id in node['interface_ids']:
                #interface = Interface(interfaces[if_id]) 
                #interface['ipv4'] = interface['ip']
                #interface['component_id'] = PlXrn(auth=self.driver.hrn, 
                                                #interface='node%s:eth%s' % (node['node_id'], if_count)).get_urn()
                # interfaces in the manifest need a client id
                #if slice:
                    #interface['client_id'] = "%s:%s" % (node['node_id'], if_id)            
                #rspec_node['interfaces'].append(interface)
                #if_count+=1
        
            #tags = [PLTag(node_tags[tag_id]) for tag_id in node['node_tag_ids']]
            rspec_node['tags'] = []
            if node['hostname'] in slivers:
                # add sliver info
                sliver = slivers[node['hostname']]
                rspec_node['sliver_id'] = sliver['sliver_id']
                rspec_node['client_id'] = node['hostname']
                rspec_node['slivers'] = [sliver]
                
                # slivers always provide the ssh service
                #login = Login({'authentication': 'ssh-keys', 'hostname': node['hostname'], 'port':'22', 'username': sliver['name']})
                #service = Services({'login': login})
                #rspec_node['services'] = [service]
            rspec_nodes.append(rspec_node)
        
        return (rspec_nodes)       

#from plc/aggregate.py 
    def get_rspec(self, slice_xrn=None, version = None, options={}):

        rspec = None
	version_manager = VersionManager()	

	version = version_manager.get_version(version)
        print>>sys.stderr, " \r\n SlabAggregate \t\t get_rspec ************** version %s version.type %s  version.version %s options %s \r\n" %(version,version.type,version.version,options)

	if not slice_xrn:
            rspec_version = version_manager._get_version(version.type, version.version, 'ad')

        else:
            rspec_version = version_manager._get_version(version.type, version.version, 'manifest')
           
        slice, slivers = self.get_slice_and_slivers(slice_xrn)
        #at this point sliver my be {} if no senslab job is running for this user/slice.
        rspec = RSpec(version=rspec_version, user_options=options)

        
        #if slice and 'expires' in slice:
           #rspec.xml.set('expires',  datetime_to_epoch(slice['expires']))
         # add sliver defaults
        #nodes, links = self.get_nodes(slice, slivers)
        nodes = self.get_nodes(slice,slivers) 
        print>>sys.stderr, " \r\n SlabAggregate \t\t get_rspec ************** options %s rspec_version %s version_manager %s  rspec.version %s \r\n" %(options, rspec_version,version_manager, rspec.version)
        rspec.version.add_nodes(nodes)


        default_sliver = slivers.get(None, [])
        if default_sliver:
            default_sliver_attribs = default_sliver.get('tags', [])
            print>>sys.stderr, " \r\n SlabAggregate \t\t get_rspec ************** default_sliver_attribs %s \r\n" %(default_sliver_attribs)
            for attrib in default_sliver_attribs:
                print>>sys.stderr, " \r\n SlabAggregate \t\t get_rspec ************** attrib %s \r\n" %(attrib)
                logger.info(attrib)
                rspec.version.add_default_sliver_attribute(attrib['tagname'], attrib['value'])   

        return rspec.toxml()          
