# 
import sys
import time,datetime
from StringIO import StringIO
from types import StringTypes
from copy import deepcopy
from copy import copy
from lxml import etree

from sfa.util.sfalogging import logger
#from sfa.util.sfalogging import sfa_logger
from sfa.util.rspecHelper import merge_rspecs
from sfa.util.xrn import Xrn, urn_to_hrn, hrn_to_urn
from sfa.util.plxrn import hrn_to_pl_slicename
from sfa.util.rspec import *
from sfa.util.specdict import *
from sfa.util.faults import *
from sfa.util.record import SfaRecord
#from sfa.rspecs.pg_rspec import PGRSpec
#from sfa.rspecs.sfa_rspec import SfaRSpec
from sfa.rspecs.rspec_converter import RSpecConverter
#from sfa.rspecs.rspec_parser import parse_rspec    
#from sfa.rspecs.rspec_version import RSpecVersion
#from sfa.rspecs.sfa_rspec import sfa_rspec_version
#from sfa.rspecs.pg_rspec import pg_rspec_ad_version, pg_rspec_request_version
from sfa.client.client_helper import sfa_to_pg_users_arg
from sfa.rspecs.version_manager import VersionManager

from sfa.rspecs.rspec import RSpec 
from sfa.util.policy import Policy
from sfa.util.prefixTree import prefixTree
from sfa.util.sfaticket import *
from sfa.trust.credential import Credential
from sfa.util.threadmanager import ThreadManager
import sfa.util.xmlrpcprotocol as xmlrpcprotocol     
import sfa.plc.peers as peers
from sfa.util.version import version_core
from sfa.util.callids import Callids

def _call_id_supported(api, server):
    """
    Returns true if server support the optional call_id arg, false otherwise.
    """
    server_version = api.get_cached_server_version(server)

    if 'sfa' in server_version:
        code_tag = server_version['code_tag']
        code_tag_parts = code_tag.split("-")

        version_parts = code_tag_parts[0].split(".")
        major, minor = version_parts[0:2]
        rev = code_tag_parts[1]
        if int(major) > 1:
            if int(minor) > 0 or int(rev) > 20:
                return True
    return False

# we have specialized xmlrpclib.ServerProxy to remember the input url
# OTOH it's not clear if we're only dealing with XMLRPCServerProxy instances
def get_serverproxy_url (server):
    try:
        return server.get_url()
    except:
        logger.warning("GetVersion, falling back to xmlrpclib.ServerProxy internals")
        return server._ServerProxy__host + server._ServerProxy__handler 

def GetVersion(api):
    # peers explicitly in aggregates.xml
    peers =dict ([ (peername,get_serverproxy_url(v)) for (peername,v) in api.aggregates.iteritems()
                   if peername != api.hrn])
    version_manager = VersionManager()
    ad_rspec_versions = []
    request_rspec_versions = []
    for rspec_version in version_manager.versions:
        if rspec_version.content_type in ['*', 'ad']:
            ad_rspec_versions.append(rspec_version.to_dict())
        if rspec_version.content_type in ['*', 'request']:
            request_rspec_versions.append(rspec_version.to_dict())
    default_rspec_version = version_manager.get_version("sfa 1").to_dict()
    xrn=Xrn(api.hrn, 'authority+sa')
    version_more = {'interface':'slicemgr',
                    'hrn' : xrn.get_hrn(),
                    'urn' : xrn.get_urn(),
                    'peers': peers,
                    'request_rspec_versions': request_rspec_versions,
                    'ad_rspec_versions': ad_rspec_versions,
                    'default_ad_rspec': default_rspec_version
                    }
    sm_version=version_core(version_more)
    # local aggregate if present needs to have localhost resolved
    if api.hrn in api.aggregates:
        local_am_url=get_serverproxy_url(api.aggregates[api.hrn])
        sm_version['peers'][api.hrn]=local_am_url.replace('localhost',sm_version['hostname'])
    return sm_version


#def GetVersion(api):
    ## peers explicitly in aggregates.xml
    #peers =dict ([ (peername,get_serverproxy_url(v)) for (peername,v) in api.aggregates.iteritems() 
                   #if peername != api.hrn])
    #xrn=Xrn (api.hrn)
    #request_rspec_versions = [dict(pg_rspec_request_version), dict(sfa_rspec_version)]
    #ad_rspec_versions = [dict(pg_rspec_ad_version), dict(sfa_rspec_version)]
    #version_more = {'interface':'slicemgr',
                    #'hrn' : xrn.get_hrn(),
                    #'urn' : xrn.get_urn(),
                    #'peers': peers,
                    #'request_rspec_versions': request_rspec_versions,
                    #'ad_rspec_versions': ad_rspec_versions,
                    #'default_ad_rspec': dict(sfa_rspec_version)
                    #}
    #sm_version=version_core(version_more)
    ## local aggregate if present needs to have localhost resolved
    #if api.hrn in api.aggregates:
        #local_am_url=get_serverproxy_url(api.aggregates[api.hrn])
        #sm_version['peers'][api.hrn]=local_am_url.replace('localhost',sm_version['hostname'])
    #return sm_version
 
 
def drop_slicemgr_stats(api,rspec):
	try:
		stats_elements = rspec.xml.xpath('//statistics')
		for node in stats_elements:
			node.getparent().remove(node)
	except Exception, e:
		api.logger.warn("drop_slicemgr_stats failed: %s " % (str(e)))
 
 
 
 
def CreateSliver(api, xrn, creds, rspec_str, users, call_id):
	version_manager = VersionManager()
	def _CreateSliver(aggregate, xrn, credential, rspec, users, call_id):
	# Need to call ParseVersion at an aggregate to determine the supported 
	# rspec type/format beofre calling CreateSliver at an Aggregate. 
	# The Aggregate's verion info is cached 
		
		tStart = time.time()
		try:
			# Need to call GetVersion at an aggregate to determine the supported
			# rspec type/format beofre calling CreateSliver at an Aggregate.
			server_version = api.get_cached_server_version(server)
			requested_users = users
			if 'sfa' not in server_version and 'geni_api' in server_version:
				# sfa aggregtes support both sfa and pg rspecs, no need to convert
				# if aggregate supports sfa rspecs. otherwise convert to pg rspec
				rspec = RSpec(RSpecConverter.to_pg_rspec(rspec, 'request'))
				filter = {'component_manager_id': server_version['urn']}
				rspec.filter(filter)
				rspec = rspec.toxml()
				requested_users = sfa_to_pg_users_arg(users)
			args = [xrn, credential, rspec, requested_users]
			if _call_id_supported(api, server):
				args.append(call_id)
			rspec = server.CreateSliver(*args)
			return {"aggregate": aggregate, "rspec": rspec, "elapsed": time.time()-tStart, "status": "success"}
		except: 
			logger.log_exc('Something wrong in _CreateSliver with URL %s'%server.url)
		return {"aggregate": aggregate, "elapsed": time.time()-tStart, "status": "exception"}

	
	if Callids().already_handled(call_id): return ""
	
	# Validate the RSpec against PlanetLab's schema --disabled for now
	# The schema used here needs to aggregate the PL and VINI schemas
	# schema = "/var/www/html/schemas/pl.rng"
	rspec = RSpec(rspec_str)
	schema = None
	if schema:
		rspec.validate(schema)
		
	print>>sys.stderr, " \r\n \r\n \t\t =======SLICE MANAGER _CreateSliver api %s" %(api)
	# if there is a <statistics> section, the aggregates don't care about it,
	# so delete it.
	drop_slicemgr_stats(api,rspec)
	
	# attempt to use delegated credential first
	credential = api.getDelegatedCredential(creds)
	if not credential:
		credential = api.getCredential()
	
	# get the callers hrn
	hrn, type = urn_to_hrn(xrn)
	valid_cred = api.auth.checkCredentials(creds, 'createsliver', hrn)[0]
	caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()
	threads = ThreadManager()
	
	for aggregate in api.aggregates:
	# prevent infinite loop. Dont send request back to caller
	# unless the caller is the aggregate's SM 
		if caller_hrn == aggregate and aggregate != api.hrn:
			continue
		interface = api.aggregates[aggregate]
		server = api.get_server(interface, credential)   
		# Just send entire RSpec to each aggregate
		threads.run(_CreateSliver, aggregate, xrn, [credential], rspec.toxml(), users, call_id)
		
	results = threads.get_results()
	manifest_version = version_manager._get_version(rspec.version.type, rspec.version.version, 'manifest')
	result_rspec = RSpec(version=manifest_version)
    #rspec = SfaRSpec()
	for result in results:
		add_slicemgr_stat(result_rspec, "CreateSliver", result["aggregate"], result["elapsed"], result["status"])
		if result["status"]=="success":
            		try:
				result_rspec.version.merge(result["rspec"])
			except:
                		api.logger.log_exc("SM.CreateSliver: Failed to merge aggregate rspec")
	return result_rspec.toxml()
        #rspec.merge(result)     
    #return rspec.toxml()

def RenewSliver(api, xrn, creds, expiration_time, call_id):
    if Callids().already_handled(call_id): return True

    (hrn, type) = urn_to_hrn(xrn)
    # get the callers hrn
    valid_cred = api.auth.checkCredentials(creds, 'renewsliver', hrn)[0]
    caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()

    # attempt to use delegated credential first
    credential = api.getDelegatedCredential(creds)
    if not credential:
        credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        # prevent infinite loop. Dont send request back to caller
        # unless the caller is the aggregate's SM
        if caller_hrn == aggregate and aggregate != api.hrn:
            continue

        server = api.aggregates[aggregate]
        threads.run(server.RenewSliver, xrn, [credential], expiration_time, call_id)
    # 'and' the results
    return reduce (lambda x,y: x and y, threads.get_results() , True)

def get_ticket(api, xrn, creds, rspec, users):
    slice_hrn, type = urn_to_hrn(xrn)
    # get the netspecs contained within the clients rspec
    aggregate_rspecs = {}
    tree= etree.parse(StringIO(rspec))
    elements = tree.findall('./network')
    for element in elements:
        aggregate_hrn = element.values()[0]
        aggregate_rspecs[aggregate_hrn] = rspec 

    # get the callers hrn
    valid_cred = api.auth.checkCredentials(creds, 'getticket', slice_hrn)[0]
    caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()

    # attempt to use delegated credential first
    credential = api.getDelegatedCredential(creds)
    if not credential:
        credential = api.getCredential() 
    threads = ThreadManager()
    for (aggregate, aggregate_rspec) in aggregate_rspecs.iteritems():
        # prevent infinite loop. Dont send request back to caller
        # unless the caller is the aggregate's SM
        if caller_hrn == aggregate and aggregate != api.hrn:
            continue
        server = None
        if aggregate in api.aggregates:
            server = api.aggregates[aggregate]
        else:
            net_urn = hrn_to_urn(aggregate, 'authority')     
            # we may have a peer that knows about this aggregate
            for agg in api.aggregates:
                target_aggs = api.aggregates[agg].get_aggregates(credential, net_urn)
                if not target_aggs or not 'hrn' in target_aggs[0]:
                    continue
                # send the request to this address 
                url = target_aggs[0]['url']
                server = xmlrpcprotocol.get_server(url, api.key_file, api.cert_file)
                # aggregate found, no need to keep looping
                break   
        if server is None:
            continue 
        threads.run(server.ParseTicket, xrn, credential, aggregate_rspec, users)

    results = threads.get_results()
    
    # gather information from each ticket 
    rspecs = []
    initscripts = []
    slivers = [] 
    object_gid = None  
    for result in results:
        agg_ticket = SfaTicket(string=result)
        attrs = agg_ticket.get_attributes()
        if not object_gid:
            object_gid = agg_ticket.get_gid_object()
        rspecs.append(agg_ticket.get_rspec())
        initscripts.extend(attrs.get('initscripts', [])) 
        slivers.extend(attrs.get('slivers', [])) 
    
    # merge info
    attributes = {'initscripts': initscripts,
                 'slivers': slivers}
    merged_rspec = merge_rspecs(rspecs) 

    # create a new ticket
    ticket = SfaTicket(subject = slice_hrn)
    ticket.set_gid_caller(api.auth.client_gid)
    ticket.set_issuer(key=api.key, subject=api.hrn)
    ticket.set_gid_object(object_gid)
    ticket.set_pubkey(object_gid.get_pubkey())
    #new_ticket.set_parent(api.auth.hierarchy.get_auth_ticket(auth_hrn))
    ticket.set_attributes(attributes)
    ticket.set_rspec(merged_rspec)
    ticket.encode()
    ticket.sign()          
    return ticket.save_to_string(save_parents=True)


def DeleteSliver(api, xrn, creds, call_id):
    if Callids().already_handled(call_id): return ""
    (hrn, type) = urn_to_hrn(xrn)
    # get the callers hrn
    valid_cred = api.auth.checkCredentials(creds, 'deletesliver', hrn)[0]
    caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()

    # attempt to use delegated credential first
    credential = api.getDelegatedCredential(creds)
    if not credential:
        credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        # prevent infinite loop. Dont send request back to caller
        # unless the caller is the aggregate's SM
        if caller_hrn == aggregate and aggregate != api.hrn:
            continue
        server = api.aggregates[aggregate]
        threads.run(server.DeleteSliver, xrn, credential, call_id)
    threads.get_results()
    return 1

def start_slice(api, xrn, creds):
    hrn, type = urn_to_hrn(xrn)

    # get the callers hrn
    valid_cred = api.auth.checkCredentials(creds, 'startslice', hrn)[0]
    caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()

    # attempt to use delegated credential first
    credential = api.getDelegatedCredential(creds)
    if not credential:
        credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        # prevent infinite loop. Dont send request back to caller
        # unless the caller is the aggregate's SM
        if caller_hrn == aggregate and aggregate != api.hrn:
            continue
        server = api.aggregates[aggregate]
        threads.run(server.Start, xrn, credential)
    threads.get_results()    
    return 1
 
def stop_slice(api, xrn, creds):
    hrn, type = urn_to_hrn(xrn)

    # get the callers hrn
    valid_cred = api.auth.checkCredentials(creds, 'stopslice', hrn)[0]
    caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()

    # attempt to use delegated credential first
    credential = api.getDelegatedCredential(creds)
    if not credential:
        credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        # prevent infinite loop. Dont send request back to caller
        # unless the caller is the aggregate's SM
        if caller_hrn == aggregate and aggregate != api.hrn:
            continue
        server = api.aggregates[aggregate]
        threads.run(server.Stop, xrn, credential)
    threads.get_results()    
    return 1

def reset_slice(api, xrn):
    """
    Not implemented
    """
    return 1

def shutdown(api, xrn, creds):
    """
    Not implemented   
    """
    return 1

def status(api, xrn, creds):
    """
    Not implemented 
    """
    return 1

# Thierry : caching at the slicemgr level makes sense to some extent
#caching=True
caching=False
def ListSlices(api, creds, call_id):

    if Callids().already_handled(call_id): return []

    # look in cache first
    if caching and api.cache:
        slices = api.cache.get('slices')
        if slices:
            return slices    

    # get the callers hrn
    valid_cred = api.auth.checkCredentials(creds, 'listslices', None)[0]
    caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()

    # attempt to use delegated credential first
    credential = api.getDelegatedCredential(creds)
    if not credential:
        credential = api.getCredential()
    threads = ThreadManager()
    # fetch from aggregates
    for aggregate in api.aggregates:
        # prevent infinite loop. Dont send request back to caller
        # unless the caller is the aggregate's SM
        if caller_hrn == aggregate and aggregate != api.hrn:
            continue
        server = api.aggregates[aggregate]
        threads.run(server.ListSlices, credential, call_id)

    # combime results
    results = threads.get_results()
    slices = []
    for result in results:
        slices.extend(result)
    
    # cache the result
    if caching and api.cache:
        api.cache.add('slices', slices)

    return slices

def add_slicemgr_stat(rspec, callname, aggname, elapsed, status):
	try:
		stats_tags = rspec.xml.xpath('//statistics[@call="%s"]' % callname)
		if stats_tags:
			stats_tag = stats_tags[0]
		else:
			stats_tag = etree.SubElement(rspec.xml.root, "statistics", call=callname)
			
		etree.SubElement(stats_tag, "aggregate", name=str(aggname), elapsed=str(elapsed), status=str(status))
	except Exception, e:
		api.logger.warn("add_slicemgr_stat failed on  %s: %s" %(aggname, str(e)))




def ListResources(api, creds, options, call_id):
    version_manager = VersionManager()
    def _ListResources(aggregate, server, credential, opts, call_id):

        my_opts = copy(opts)
        args = [credential, my_opts]
        tStart = time.time()
        try:
            if _call_id_supported(api, server):
                args.append(call_id)
            version = api.get_cached_server_version(server)
            # force ProtoGENI aggregates to give us a v2 RSpec
            if 'sfa' not in version.keys():
                my_opts['rspec_version'] = version_manager.get_version('ProtoGENI 2').to_dict()
            rspec = server.ListResources(*args)
            return {"aggregate": aggregate, "rspec": rspec, "elapsed": time.time()-tStart, "status": "success"}
        except Exception, e:
            api.logger.log_exc("ListResources failed at %s" %(server.url))
            return {"aggregate": aggregate, "elapsed": time.time()-tStart, "status": "exception"}

    if Callids().already_handled(call_id): return ""

    # get slice's hrn from options
    xrn = options.get('geni_slice_urn', '')
    (hrn, type) = urn_to_hrn(xrn)
    if 'geni_compressed' in options:
        del(options['geni_compressed'])

    # get the rspec's return format from options
    rspec_version = version_manager.get_version(options.get('rspec_version'))
    version_string = "rspec_%s" % (rspec_version.to_string())

    # look in cache first
    if caching and api.cache and not xrn:
        rspec =  api.cache.get(version_string)
        if rspec:
            return rspec

    # get the callers hrn
    valid_cred = api.auth.checkCredentials(creds, 'listnodes', hrn)[0]
    caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()

    # attempt to use delegated credential first
    cred = api.getDelegatedCredential(creds)
    if not cred:
        cred = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        # prevent infinite loop. Dont send request back to caller
        # unless the caller is the aggregate's SM
        if caller_hrn == aggregate and aggregate != api.hrn:
            continue

        # get the rspec from the aggregate
        interface = api.aggregates[aggregate]
        server = api.get_server(interface, cred)
        threads.run(_ListResources, aggregate, server, [cred], options, call_id)


    results = threads.get_results()
    rspec_version = version_manager.get_version(options.get('rspec_version'))
    if xrn:    
        result_version = version_manager._get_version(rspec_version.type, rspec_version.version, 'manifest')
    else: 
        result_version = version_manager._get_version(rspec_version.type, rspec_version.version, 'ad')
    rspec = RSpec(version=result_version)
    for result in results:
        add_slicemgr_stat(rspec, "ListResources", result["aggregate"], result["elapsed"], result["status"])
        if result["status"]=="success":
            try:
                rspec.version.merge(result["rspec"])
            except:
                api.logger.log_exc("SM.ListResources: Failed to merge aggregate rspec")

    # cache the result
    if caching and api.cache and not xrn:
        api.cache.add(version_string, rspec.toxml())
	
    print >>sys.stderr, "\r\n  slice_manager  \r\n"   , rspec
    return rspec.toxml()

#def ListResources(api, creds, options, call_id):

    #if Callids().already_handled(call_id): return ""

    ## get slice's hrn from options
    #xrn = options.get('geni_slice_urn', '')
    #(hrn, type) = urn_to_hrn(xrn)
    #print >>sys.stderr, " SM_ListResources xrn " , xrn
    ##print >>sys.stderr, " SM ListResources api.__dict__ " , api.__dict__.keys()
    ##print >>sys.stderr, " SM ListResources dir(api)" , dir(api)
    #print >>sys.stderr, "  \r\n avant RspecVersion \r\n \r\n"
    ## get the rspec's return format from options
    #rspec_version = RSpecVersion(options.get('rspec_version'))
    #print >>sys.stderr, " \r\n \r\n ListResources RSpecVersion ", rspec_version
    #version_string = "rspec_%s" % (rspec_version.get_version_name())

    ##panos adding the info option to the caching key (can be improved)
    #if options.get('info'):
	#version_string = version_string + "_"+options.get('info')
   
    #print>>sys.stderr,"version string = ",version_string

    ## look in cache first
    #if caching and api.cache and not xrn:
	#print>>sys.stderr," \r\n  caching %s and api.cache %s and not xrn %s"%(caching , api.cache,xrn) 
        #rspec =  api.cache.get(version_string)
        #if rspec:
            #return rspec

    ## get the callers hrn
    #print >>sys.stderr, " SM ListResources get the callers hrn "
    #valid_cred = api.auth.checkCredentials(creds, 'listnodes', hrn)[0]
    #caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()
    #print >>sys.stderr, " \r\n SM ListResources get the callers caller_hrn hrn  %s "%(caller_hrn)
    ## attempt to use delegated credential first
    #credential = api.getDelegatedCredential(creds)
    #print >>sys.stderr, " \r\n SM ListResources get the callers credential  %s "%(credential) 
    #if not credential:
        #credential = api.getCredential()
    #threads = ThreadManager()
    #print >>sys.stderr, " \r\n SM ListResources get the callers api.aggregates  %s "%(api.aggregates) 
    #for aggregate in api.aggregates:
        ## prevent infinite loop. Dont send request back to caller
        ## unless the caller is the aggregate's SM
        #if caller_hrn == aggregate and aggregate != api.hrn:
            #continue
        ## get the rspec from the aggregate
        #server = api.aggregates[aggregate]
	#print >>sys.stderr, " Slice Mgr ListResources, server" ,server
        #my_opts = copy(options)
        #my_opts['geni_compressed'] = False
        #threads.run(server.ListResources, credential, my_opts, call_id)
        #print >>sys.stderr, "\r\n  !!!!!!!!!!!!!!!! \r\n"       
    #results = threads.get_results()
    ##results.append(open('/root/protogeni.rspec', 'r').read())
    #rspec_version = RSpecVersion(my_opts.get('rspec_version'))
    #if rspec_version['type'].lower() == 'protogeni':
        #rspec = PGRSpec()
    #else:
        #rspec = SfaRSpec()

    #for result in results:
        #print >>sys.stderr, "\r\n  slice_manager  result"   , result
        #try:
            #print >>sys.stderr, "avant merge"  , rspec         
            #rspec.merge(result)        
            #print >>sys.stderr, "AFTERMERGE" , rspec
        #except:
            #raise
            #api.logger.info("SM.ListResources: Failed to merge aggregate rspec")

    ## cache the result
    #if caching and api.cache and not xrn:
        #api.cache.add(version_string, rspec.toxml())

    #print >>sys.stderr, "\r\n  slice_manager  \r\n"   , rspec
    #return rspec.toxml()

# first draft at a merging SliverStatus
def SliverStatus(api, slice_xrn, creds, call_id):
    if Callids().already_handled(call_id): return {}
    # attempt to use delegated credential first
    credential = api.getDelegatedCredential(creds)
    if not credential:
        credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        server = api.aggregates[aggregate]
        threads.run (server.SliverStatus, slice_xrn, credential, call_id)
    results = threads.get_results()

    # get rid of any void result - e.g. when call_id was hit where by convention we return {}
    results = [ result for result in results if result and result['geni_resources']]

    # do not try to combine if there's no result
    if not results : return {}

    # otherwise let's merge stuff
    overall = {}

    # mmh, it is expected that all results carry the same urn
    overall['geni_urn'] = results[0]['geni_urn']

    # consolidate geni_status - simple model using max on a total order
    states = [ 'ready', 'configuring', 'failed', 'unknown' ]
    # hash name to index
    shash = dict ( zip ( states, range(len(states)) ) )
    def combine_status (x,y):
        return shash [ max (shash(x),shash(y)) ]
    overall['geni_status'] = reduce (combine_status, [ result['geni_status'] for result in results], 'ready' )

    # {'ready':0,'configuring':1,'failed':2,'unknown':3}
    # append all geni_resources
    overall['geni_resources'] = \
        reduce (lambda x,y: x+y, [ result['geni_resources'] for result in results] , [])

    return overall

def main():
    r = RSpec()
    r.parseFile(sys.argv[1])
    rspec = r.toDict()
    CreateSliver(None,'plc.princeton.tmacktestslice',rspec,'create-slice-tmacktestslice')

if __name__ == "__main__":
    main()
    
