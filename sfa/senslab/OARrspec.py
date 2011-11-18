
#!/usr/bin/python

# import modules used here -- sys is a very standard one
import sys
import httplib
import json


from sfa.util.xrn import *
from sfa.util.plxrn import *
#from sfa.rspecs.sfa_rspec import SfaRSpec
from sfa.rspecs.rspec import RSpec
#from sfa.rspecs.pg_rspec  import PGRSpec
#from sfa.rspecs.rspec_version import RSpecVersion
from sfa.rspecs.version_manager import VersionManager
from sfa.senslab.OARrestapi import *
from sfa.senslab.slabdriver import SlabDriver
from sfa.util.config import Config

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

    def __init__(self ,api, user_options={}):
	self.OARImporter = OARapi()	
        self.driver = SlabDriver(Config())
	self.user_options = user_options
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
		print >>sys.stderr,'prepare_nodes:node', node

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
                node['urn'] = hostname_to_urn(node['network'], node['site_login_base'], node['hostname'])
                node['site_urn'] = hrn_to_urn(PlXrn.site_hrn(node['network'], node['site_login_base']), 'authority+sa') 
                #node['site'] = site
                #node['interfaces'] = interfaces
                #node['tags'] = tags
		#print >>sys.stderr, "\r\n OAR  prepare ", node 
		
        self.prepared = True  
	print >>sys.stderr, " \r\n \t\t prepare prepare_nodes \r\n %s " %(self.nodes)
#from plc/aggregate.py 
    def get_rspec(self, slice_xrn=None, version = None):
	print>>sys.stderr, " \r\n OARrspec \t\t get_spec **************\r\n" 
        self.prepare()
	
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
        rspec.version.add_nodes(self.nodes.values())
	print >>sys.stderr, 'after add_nodes'
      

        #rspec.add_links(self.links.values())

        #if slice_xrn:
            ## get slice details
            #slice_hrn, _ = urn_to_hrn(slice_xrn)
            #slice_name = hrn_to_pl_slicename(slice_hrn)
            #slices = self.api.plshell.GetSlices(self.api.plauth, slice_name)
            #if slices:
                #slice = slices[0]
                #slivers = []
                #tags = self.api.plshell.GetSliceTags(self.api.plauth, slice['slice_tag_ids'])
                #for node_id in slice['node_ids']:
                    #sliver = {}
                    #sliver['hostname'] = self.nodes[node_id]['hostname']
                    #sliver['tags'] = []
                    #slivers.append(sliver)
                    #for tag in tags:
                        ## if tag isn't bound to a node then it applies to all slivers
                        #if not tag['node_id']:
                            #sliver['tags'].append(tag)
                        #else:
                            #tag_host = self.nodes[tag['node_id']]['hostname']
                            #if tag_host == sliver['hostname']:
                                #sliver.tags.append(tag)
                #rspec.add_slivers(slivers)
        return rspec.toxml()          
