###########################################################################
#    Copyright (C) 2011 by root                                      
#    <root@FlabFedora2>                                                             
#
# Copyright: See COPYING file that comes with this distribution
#
###########################################################################
#!/usr/bin/python

# import modules used here -- sys is a very standard one
import sys
import httplib
import json


from sfa.util.xrn import *
from sfa.util.plxrn import *
from sfa.rspecs.sfa_rspec import SfaRSpec
from sfa.rspecs.pg_rspec  import PGRSpec
from sfa.rspecs.rspec_version import RSpecVersion

from sfa.senslab.OARrestapi import *

class OARrspec:

    
    sites = {}
    nodes = {}
  
    prepared=False
    #panos new user options variable
    user_options = {}

    def __init__(self):
	self.OARImporter = OARapi()	
	print >>sys.stderr,'\r\n \r\n \t\t__INIT OARRSPEC__'


    def prepare_sites(self, force=False):
	print >>sys.stderr,'\r\n \r\n ++++++++++++++\t\t',  self.OARImporter.GetSites()
        if not self.sites or force:  
             for site in self.OARImporter.GetSites():
		print >>sys.stderr,'prepare_sites : site ', site		    
                self.sites[site['site_id']] = site
	
    
    def prepare_nodes(self, force=False):
        if not self.nodes or force:
            for node in self.OARImporter.GetNodes():
                self.nodes[node['node_id']] = node
		print >>sys.stderr,'prepare_nodes:node', node



    #def prepare_node_tags(self, force=False):
        #if not self.node_tags or force:
            #for node_tag in self.api.plshell.GetNodeTags(self.api.plauth):
                #self.node_tags[node_tag['node_tag_id']] = node_tag


    def prepare(self, force=False):
        if not self.prepared or force:
            self.prepare_sites(force)
            self.prepare_nodes(force)
        
            # add site/interface info to nodes
            for node_id in self.nodes:
                node = self.nodes[node_id]
                site = self.sites[node['site_id']]
              
		node['network'] = "grenoble-senslab"	
                node['network_urn'] = hrn_to_urn(node['network'], 'authority+sa')
                node['urn'] = hostname_to_urn(node['network'], site['login_base'], node['hostname'])
                node['site_urn'] = hrn_to_urn(PlXrn.site_hrn(node['network'], site['login_base']), 'authority') 
                node['site'] = site
             
                #node['tags'] = tags
	print >>sys.stderr, "\r\n OAR  prepare ", node 
        self.prepared = True  

    def get_rspec(self, slice_xrn=None, version = None):
	print>>sys.stderr, " \r\n OARrspec \t\t get_spec **************\r\n" 
        self.prepare()
	
        rspec = None
        rspec_version = RSpecVersion(version)
	print >>sys.stderr, '\r\n \t\t rspec_version type', rspec_version['type']
        if rspec_version['type'].lower() == 'sfa':
            rspec = SfaRSpec("",{},self.user_options)
        else:
            rspec = SfaRSpec("",{},self.user_options)


        rspec.add_nodes(self.nodes.values())
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
