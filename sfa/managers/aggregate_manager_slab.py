#!/usr/bin/python

import datetime
import time
import traceback
import sys
import re
from types import StringTypes

from sfa.util.faults import *
from sfa.util.xrn import get_authority, hrn_to_urn, urn_to_hrn, Xrn, urn_to_sliver_id
from sfa.util.plxrn import slicename_to_hrn, hrn_to_pl_slicename, hostname_to_urn
from sfa.util.rspec import *
from sfa.util.specdict import *
from sfa.util.record import SfaRecord
from sfa.util.policy import Policy
from sfa.util.record import *
from sfa.util.sfaticket import SfaTicket

from sfa.senslab.slices import *

from sfa.trust.credential import Credential
import sfa.plc.peers as peers
from sfa.plc.network import *
from sfa.senslab.OARrestapi import *
from sfa.senslab.api import SfaAPI
#from sfa.plc.aggregate import Aggregate
#from sfa.plc.slices import *
from sfa.util.version import version_core
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec
from sfa.util.sfatime import utcparse
from sfa.util.callids import Callids
from sfa.senslab.OARrspec import *
#from sfa.plc.aggregate import Aggregate

def GetVersion(api):
	print>>sys.stderr, "\r\n AGGREGATE GET_VERSION "
	#xrn=Xrn(api.hrn)
	#supported_rspecs = [dict(pg_rspec_request_version), dict(sfa_rspec_version)]
	#ad_rspec_versions = [dict(pg_rspec_ad_version), dict(sfa_rspec_version)]
	version_manager = VersionManager()
	ad_rspec_versions = []
	request_rspec_versions = []
	for rspec_version in version_manager.versions:
		if rspec_version.content_type in ['*', 'ad']:
			ad_rspec_versions.append(rspec_version.to_dict())
		if rspec_version.content_type in ['*', 'request']:
			request_rspec_versions.append(rspec_version.to_dict()) 
	default_rspec_version = version_manager.get_version("sfa 1").to_dict()
	xrn=Xrn(api.hrn)
	version_more = {'interface':'aggregate',
			'testbed':'senslab',
			'hrn':xrn.get_hrn(),
			'request_rspec_versions': request_rspec_versions,
			'ad_rspec_versions': ad_rspec_versions,
			'default_ad_rspec': default_rspec_version
			}
	print>>sys.stderr, "\r\n AGGREGATE GET_VERSION : %s  \r\n \r\n" %(version_core(version_more))	    
	return version_core(version_more)

def __get_registry_objects(slice_xrn, creds, users):
    """

    """
    hrn, type = urn_to_hrn(slice_xrn)

    hrn_auth = get_authority(hrn)

    # Build up objects that an SFA registry would return if SFA
    # could contact the slice's registry directly
    reg_objects = None

    if users:
        # dont allow special characters in the site login base
        #only_alphanumeric = re.compile('[^a-zA-Z0-9]+')
        #login_base = only_alphanumeric.sub('', hrn_auth[:20]).lower()
        slicename = hrn_to_pl_slicename(hrn)
        login_base = slicename.split('_')[0]
        reg_objects = {}
        site = {}
        site['site_id'] = 0
        site['name'] = 'geni.%s' % login_base 
        site['enabled'] = True
        site['max_slices'] = 100

        # Note:
        # Is it okay if this login base is the same as one already at this myplc site?
        # Do we need uniqueness?  Should use hrn_auth instead of just the leaf perhaps?
        site['login_base'] = login_base
        site['abbreviated_name'] = login_base
        site['max_slivers'] = 1000
        reg_objects['site'] = site

        slice = {}
        
        #extime = Credential(string=creds[0]).get_expiration()
        ## If the expiration time is > 60 days from now, set the expiration time to 60 days from now
        #if extime > datetime.datetime.utcnow() + datetime.timedelta(days=60):
        extime = datetime.datetime.utcnow() + datetime.timedelta(days=60)
        slice['expires'] = int(time.mktime(extime.timetuple()))
        slice['hrn'] = hrn
        slice['name'] = hrn_to_pl_slicename(hrn)
        slice['url'] = hrn
        slice['description'] = hrn
        slice['pointer'] = 0
        reg_objects['slice_record'] = slice

        reg_objects['users'] = {}
        for user in users:
            user['key_ids'] = []
            hrn, _ = urn_to_hrn(user['urn'])
            user['email'] = hrn_to_pl_slicename(hrn) + "@geni.net"
            user['first_name'] = hrn
            user['last_name'] = hrn
            reg_objects['users'][user['email']] = user

        return reg_objects

def __get_hostnames(nodes):
    hostnames = []
    for node in nodes:
        hostnames.append(node.hostname)
    return hostnames

def SliverStatus(api, slice_xrn, creds, call_id):
    if Callids().already_handled(call_id): return {}

    (hrn, type) = urn_to_hrn(slice_xrn)
    # find out where this slice is currently running
    api.logger.info(hrn)
    slicename = hrn_to_pl_slicename(hrn)
    
    slices = api.plshell.GetSlices(api.plauth, [slicename], ['node_ids','person_ids','name','expires'])
    if len(slices) == 0:        
        raise Exception("Slice %s not found (used %s as slicename internally)" % slice_xrn, slicename)
    slice = slices[0]
    
    # report about the local nodes only
    nodes = api.plshell.GetNodes(api.plauth, {'node_id':slice['node_ids'],'peer_id':None},
                                 ['hostname', 'site_id', 'boot_state', 'last_contact'])
    site_ids = [node['site_id'] for node in nodes]
    sites = api.plshell.GetSites(api.plauth, site_ids, ['site_id', 'login_base'])
    sites_dict = dict ( [ (site['site_id'],site['login_base'] ) for site in sites ] )

    result = {}
    top_level_status = 'unknown'
    if nodes:
        top_level_status = 'ready'
    result['geni_urn'] = Xrn(slice_xrn, 'slice').get_urn()
    result['pl_login'] = slice['name']
    result['pl_expires'] = datetime.datetime.fromtimestamp(slice['expires']).ctime()
    
    resources = []
    for node in nodes:
        res = {}
        res['pl_hostname'] = node['hostname']
        res['pl_boot_state'] = node['boot_state']
        res['pl_last_contact'] = node['last_contact']
        if node['last_contact'] is not None:
            res['pl_last_contact'] = datetime.datetime.fromtimestamp(node['last_contact']).ctime()
        res['geni_urn'] = hostname_to_urn(api.hrn, sites_dict[node['site_id']], node['hostname'])
        if node['boot_state'] == 'boot':
            res['geni_status'] = 'ready'
        else:
            res['geni_status'] = 'failed'
            top_level_staus = 'failed' 
            
        res['geni_error'] = ''

        resources.append(res)
        
    result['geni_status'] = top_level_status
    result['geni_resources'] = resources
    # XX remove me
    #api.logger.info(result)
    # XX remove me
    return result

def CreateSliver(api, slice_xrn, creds, rspec_string, users, call_id):
    """
    Create the sliver[s] (slice) at this aggregate.    
    Verify HRN and initialize the slice record in PLC if necessary.
    """
    print>>sys.stderr, " \r\n AGGREGATE CreateSliver-----------------> "
    if Callids().already_handled(call_id): return ""

    #reg_objects = __get_registry_objects(slice_xrn, creds, users)
    #aggregate = Aggregate(api)
    aggregate = OARrspec(api)
    print>>sys.stderr, " \r\n AGGREGATE CreateSliver DAFUQ IS THIS ?-----------------> aggregate " , aggregate
    slices = Slices(api)    
    print>>sys.stderr, " \r\n AGGREGATE CreateSliver DAFUQ IS THAT ?-----------------> Slices " , slices
    (hrn, type) = urn_to_hrn(slice_xrn)
    
    peer = slices.get_peer(hrn)
    sfa_peer = slices.get_sfa_peer(hrn)
    slice_record=None
    if users:
        slice_record = users[0].get('slice_record', {})
	    
    #registry = api.registries[api.hrn]
    #credential = api.getCredential()
    #(site_id, remote_site_id) = slices.verify_site(registry, credential, hrn, 
                                                   #peer, sfa_peer, reg_objects)
    # parse rspec
    rspec = RSpec(rspec_string)
    requested_attributes = rspec.version.get_slice_attributes()
    
    # ensure site record exists
    site = slices.verify_site(hrn, slice_record, peer, sfa_peer)
    # ensure slice record exists
    slice = slices.verify_slice(hrn, slice_record, peer, sfa_peer)
    # ensure person records exists
    persons = slices.verify_persons(hrn, slice, users, peer, sfa_peer)
    # ensure slice attributes exists
    slices.verify_slice_attributes(slice, requested_attributes)
    
    # add/remove slice from nodes
    requested_slivers = [str(host) for host in rspec.version.get_nodes_with_slivers()]
    slices.verify_slice_nodes(slice, requested_slivers, peer)
     
     
       
    #nodes = api.oar.GetNodes(slice['node_ids'], ['hostname'])
    #current_slivers = [node['hostname'] for node in nodes] 
    #rspec = parse_rspec(rspec_string)
    #requested_slivers = [str(host) for host in rspec.get_nodes_with_slivers()]
    ## remove nodes not in rspec
    #deleted_nodes = list(set(current_slivers).difference(requested_slivers))

    ## add nodes from rspec
    #added_nodes = list(set(requested_slivers).difference(current_slivers))

    #try:
        #if peer:
            #api.plshell.UnBindObjectFromPeer(api.plauth, 'slice', slice['slice_id'], peer)

        #api.plshell.AddSliceToNodes(api.plauth, slice['name'], added_nodes) 
        #api.plshell.DeleteSliceFromNodes(api.plauth, slice['name'], deleted_nodes)

        ## TODO: update slice tags
        ##network.updateSliceTags()

    #finally:
        #if peer:
            #api.plshell.BindObjectToPeer(api.plauth, 'slice', slice.id, peer, 
                                         #slice.peer_id)
    # hanlde MyPLC peer association.
    # only used by plc and ple.
    #slices.handle_peer(site, slice, persons, peer)
    
    return aggregate.get_rspec(slice_xrn=slice_xrn, version=rspec.version)


def RenewSliver(api, xrn, creds, expiration_time, call_id):
    if Callids().already_handled(call_id): return True
    (hrn, type) = urn_to_hrn(xrn)
    slicename = hrn_to_pl_slicename(hrn)
    slices = api.plshell.GetSlices(api.plauth, {'name': slicename}, ['slice_id'])
    if not slices:
        raise RecordNotFound(hrn)
    slice = slices[0]
    requested_time = utcparse(expiration_time)
    record = {'expires': int(time.mktime(requested_time.timetuple()))}
    try:
        api.plshell.UpdateSlice(api.plauth, slice['slice_id'], record)
        return True
    except:
        return False

def start_slice(api, xrn, creds):
    hrn, type = urn_to_hrn(xrn)
    slicename = hrn_to_pl_slicename(hrn)
    slices = api.plshell.GetSlices(api.plauth, {'name': slicename}, ['slice_id'])
    if not slices:
        raise RecordNotFound(hrn)
    slice_id = slices[0]['slice_id']
    slice_tags = api.plshell.GetSliceTags(api.plauth, {'slice_id': slice_id, 'tagname': 'enabled'}, ['slice_tag_id'])
    # just remove the tag if it exists
    if slice_tags:
        api.plshell.DeleteSliceTag(api.plauth, slice_tags[0]['slice_tag_id'])

    return 1
 
def stop_slice(api, xrn, creds):
    hrn, type = urn_to_hrn(xrn)
    slicename = hrn_to_pl_slicename(hrn)
    slices = api.plshell.GetSlices(api.plauth, {'name': slicename}, ['slice_id'])
    if not slices:
        raise RecordNotFound(hrn)
    slice_id = slices[0]['slice_id']
    slice_tags = api.plshell.GetSliceTags(api.plauth, {'slice_id': slice_id, 'tagname': 'enabled'})
    if not slice_tags:
        api.plshell.AddSliceTag(api.plauth, slice_id, 'enabled', '0')
    elif slice_tags[0]['value'] != "0":
        tag_id = attributes[0]['slice_tag_id']
        api.plshell.UpdateSliceTag(api.plauth, tag_id, '0')
    return 1

def reset_slice(api, xrn):
    # XX not implemented at this interface
    return 1

def DeleteSliver(api, xrn, creds, call_id):
    if Callids().already_handled(call_id): return ""
    (hrn, type) = urn_to_hrn(xrn)
    slicename = hrn_to_pl_slicename(hrn)
    slices = api.plshell.GetSlices(api.plauth, {'name': slicename})
    if not slices:
        return 1
    slice = slices[0]

    # determine if this is a peer slice
    peer = peers.get_peer(api, hrn)
    try:
        if peer:
            api.plshell.UnBindObjectFromPeer(api.plauth, 'slice', slice['slice_id'], peer)
        api.plshell.DeleteSliceFromNodes(api.plauth, slicename, slice['node_ids'])
    finally:
        if peer:
            api.plshell.BindObjectToPeer(api.plauth, 'slice', slice['slice_id'], peer, slice['peer_slice_id'])
    return 1

# xxx Thierry : caching at the aggregate level sounds wrong...
#caching=True
caching=False
def ListSlices(api, creds, call_id):
    if Callids().already_handled(call_id): return []
    # look in cache first
    if caching and api.cache:
        slices = api.cache.get('slices')
        if slices:
            return slices

    # get data from db 
    slices = api.plshell.GetSlices(api.plauth, {'peer_id': None}, ['name'])
    slice_hrns = [slicename_to_hrn(api.hrn, slice['name']) for slice in slices]
    slice_urns = [hrn_to_urn(slice_hrn, 'slice') for slice_hrn in slice_hrns]

    # cache the result
    if caching and api.cache:
        api.cache.add('slices', slice_urns) 

    return slice_urns
    
    #ajouter caching cf pl manager
def ListResources(api, creds, options,call_id):

    print >>sys.stderr, 'RESOURCES AGGREGATE'
    OARImporter = OARapi()

    if Callids().already_handled(call_id): return ""
    # get slice's hrn from options
    xrn = options.get('geni_slice_urn', '')
    (hrn, type) = urn_to_hrn(xrn)
    
    version_manager = VersionManager()
    # get the rspec's return format from options
    rspec_version = version_manager.get_version(options.get('rspec_version'))
    version_string = "rspec_%s" % (rspec_version.to_string())

    #panos adding the info option to the caching key (can be improved)
    if options.get('info'):
	version_string = version_string + "_"+options.get('info', 'default')
	
    print >>sys.stderr, "[aggregate] version string = %s "%(version_string)
    
    # look in cache first
    if caching and api.cache and not xrn:
        rspec = api.cache.get(version_string)
        if rspec:
            api.logger.info("aggregate.ListResources: returning cached value for hrn %s"%hrn)
            return rspec 

    #panos: passing user-defined options
    #print "manager options = ",options
    OAR_rspec = OARrspec(api,options)
    #aggregate = Aggregate(api, options)
    rspec =  OAR_rspec.get_rspec(slice_xrn=xrn, version=rspec_version)

    # cache the result
    if caching and api.cache and not xrn:
        api.cache.add(version_string, rspec)
	
    #if rspec_version['type'].lower() == 'protogeni':
	#spec = PGRSpec()
	##panos pass user options to SfaRSpec
    #elif rspec_version['type'].lower() == 'sfa':
        #rspec = SfaRSpec("",{},options)
    #else:
        #rspec = SfaRSpec("",{},options)


    rspec =  OAR_rspec.get_rspec(slice_xrn=xrn, version=rspec_version)
    print >>sys.stderr, '\r\n OARImporter.GetNodes()', 	OARImporter.GetNodes()

    print >>sys.stderr, '  \r\n **************RSPEC' , rspec

 
    return rspec


def get_ticket(api, xrn, creds, rspec, users):

    reg_objects = __get_registry_objects(xrn, creds, users)

    slice_hrn, type = urn_to_hrn(xrn)
    slices = Slices(api)
    peer = slices.get_peer(slice_hrn)
    sfa_peer = slices.get_sfa_peer(slice_hrn)

    # get the slice record
    registry = api.registries[api.hrn]
    credential = api.getCredential()
    records = registry.Resolve(xrn, credential)

    # similar to CreateSliver, we must verify that the required records exist
    # at this aggregate before we can issue a ticket
    site_id, remote_site_id = slices.verify_site(registry, credential, slice_hrn,
                                                 peer, sfa_peer, reg_objects)
    slice = slices.verify_slice(registry, credential, slice_hrn, site_id,
                                remote_site_id, peer, sfa_peer, reg_objects)

    # make sure we get a local slice record
    record = None
    for tmp_record in records:
        if tmp_record['type'] == 'slice' and \
           not tmp_record['peer_authority']:
            record = SliceRecord(dict=tmp_record)
    if not record:
        raise RecordNotFound(slice_hrn)

    # get sliver info
    slivers = Slices(api).get_slivers(slice_hrn)
    if not slivers:
        raise SliverDoesNotExist(slice_hrn)

    # get initscripts
    initscripts = []
    data = {
        'timestamp': int(time.time()),
        'initscripts': initscripts,
        'slivers': slivers
    }

    # create the ticket
    object_gid = record.get_gid_object()
    new_ticket = SfaTicket(subject = object_gid.get_subject())
    new_ticket.set_gid_caller(api.auth.client_gid)
    new_ticket.set_gid_object(object_gid)
    new_ticket.set_issuer(key=api.key, subject=api.hrn)
    new_ticket.set_pubkey(object_gid.get_pubkey())
    new_ticket.set_attributes(data)
    new_ticket.set_rspec(rspec)
    #new_ticket.set_parent(api.auth.hierarchy.get_auth_ticket(auth_hrn))
    new_ticket.encode()
    new_ticket.sign()

    return new_ticket.save_to_string(save_parents=True)



def main():
    api = SfaAPI()
    """
    rspec = ListResources(api, "plc.princeton.sapan", None, 'pl_test_sapan')
    #rspec = ListResources(api, "plc.princeton.coblitz", None, 'pl_test_coblitz')
    #rspec = ListResources(api, "plc.pl.sirius", None, 'pl_test_sirius')
    print rspec
    """
    f = open(sys.argv[1])
    xml = f.read()
    f.close()
    CreateSliver(api, "plc.princeton.sapan", xml, 'CreateSliver_sapan')

if __name__ == "__main__":
    main()
