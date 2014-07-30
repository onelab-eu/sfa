import sys
import time
import traceback
from StringIO import StringIO
from copy import copy
from lxml import etree

from sfa.trust.sfaticket import SfaTicket
from sfa.trust.credential import Credential

from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, urn_to_hrn
from sfa.util.version import version_core
from sfa.util.callids import Callids
from sfa.util.cache import Cache

from sfa.client.multiclient import MultiClient

from sfa.rspecs.rspec_converter import RSpecConverter
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec 

from sfa.client.client_helper import sfa_to_pg_users_arg
from sfa.client.return_value import ReturnValue

class SliceManager:

    # the cache instance is a class member so it survives across incoming requests
    cache = None

    def __init__ (self, config):
        self.cache=None
        if config.SFA_SM_CACHING:
            if SliceManager.cache is None:
                SliceManager.cache = Cache()
            self.cache = SliceManager.cache
        
    def GetVersion(self, api, options):
        # peers explicitly in aggregates.xml
        peers =dict ([ (peername,interface.get_url()) for (peername,interface) in api.aggregates.iteritems()
                       if peername != api.hrn])
        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        cred_types = [{'geni_type': 'geni_sfa', 'geni_version': str(i)} for i in range(4)[-2:]]
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict())
        xrn=Xrn(api.hrn, 'authority+sm')
        version_more = {
            'interface':'slicemgr',
            'sfa': 2,
            'geni_api': 3,
            'geni_api_versions': {'3': 'http://%s:%s' % (api.config.SFA_SM_HOST, api.config.SFA_SM_PORT)},
            'hrn' : xrn.get_hrn(),
            'urn' : xrn.get_urn(),
            'peers': peers,
            'geni_single_allocation': 0, # Accept operations that act on as subset of slivers in a given state.
            'geni_allocate': 'geni_many',# Multiple slivers can exist and be incrementally added, including those which connect or overlap in some way.
            'geni_credential_types': cred_types,
            }
        sm_version=version_core(version_more)
        # local aggregate if present needs to have localhost resolved
        if api.hrn in api.aggregates:
            local_am_url=api.aggregates[api.hrn].get_url()
            sm_version['peers'][api.hrn]=local_am_url.replace('localhost',sm_version['hostname'])
        return sm_version
    
    def drop_slicemgr_stats(self, rspec):
        try:
            stats_elements = rspec.xml.xpath('//statistics')
            for node in stats_elements:
                node.getparent().remove(node)
        except Exception, e:
            logger.warn("drop_slicemgr_stats failed: %s " % (str(e)))
    
    def add_slicemgr_stat(self, rspec, callname, aggname, elapsed, status, exc_info=None):
        try:
            stats_tags = rspec.xml.xpath('//statistics[@call="%s"]' % callname)
            if stats_tags:
                stats_tag = stats_tags[0]
            else:
                stats_tag = rspec.xml.root.add_element("statistics", call=callname)

            stat_tag = stats_tag.add_element("aggregate", name=str(aggname), 
                                             elapsed=str(elapsed), status=str(status))

            if exc_info:
                exc_tag = stat_tag.add_element("exc_info", name=str(exc_info[1]))

                # formats the traceback as one big text blob
                #exc_tag.text = "\n".join(traceback.format_exception(exc_info[0], exc_info[1], exc_info[2]))

                # formats the traceback as a set of xml elements
                tb = traceback.extract_tb(exc_info[2])
                for item in tb:
                    exc_frame = exc_tag.add_element("tb_frame", filename=str(item[0]), 
                                                    line=str(item[1]), func=str(item[2]), code=str(item[3]))

        except Exception, e:
            logger.warn("add_slicemgr_stat failed on  %s: %s" %(aggname, str(e)))
    
    def ListResources(self, api, creds, options):
        call_id = options.get('call_id') 
        if Callids().already_handled(call_id): return ""

        version_manager = VersionManager()

        def _ListResources(aggregate, server, credential, options):
            forward_options = copy(options)
            tStart = time.time()
            try:
                version = api.get_cached_server_version(server)
                # force ProtoGENI aggregates to give us a v2 RSpec
                forward_options['geni_rspec_version'] = options.get('geni_rspec_version')
                result = server.ListResources(credential, forward_options)
                return {"aggregate": aggregate, "result": result, "elapsed": time.time()-tStart, "status": "success"}
            except Exception, e:
                api.logger.log_exc("ListResources failed at %s" %(server.url))
                return {"aggregate": aggregate, "elapsed": time.time()-tStart, "status": "exception", "exc_info": sys.exc_info()}
    
        # get slice's hrn from options
        xrn = options.get('geni_slice_urn', '')
        (hrn, type) = urn_to_hrn(xrn)
        if 'geni_compressed' in options:
            del(options['geni_compressed'])
    
        # get the rspec's return format from options
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        version_string = "rspec_%s" % (rspec_version)
    
        # look in cache first
        cached_requested = options.get('cached', True)
        if not xrn and self.cache and cached_requested:
            rspec =  self.cache.get(version_string)
            if rspec:
                api.logger.debug("SliceManager.ListResources returns cached advertisement")
                return rspec
    
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'listnodes', hrn)[0]
        caller_hrn = Credential(cred=valid_cred).get_gid_caller().get_hrn()
    
        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
    
            # get the rspec from the aggregate
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            multiclient.run(_ListResources, aggregate, server, [cred], options)
    
    
        results = multiclient.get_results()
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        if xrn:    
            result_version = version_manager._get_version(rspec_version.type, rspec_version.version, 'manifest')
        else: 
            result_version = version_manager._get_version(rspec_version.type, rspec_version.version, 'ad')
        rspec = RSpec(version=result_version)
        for result in results:
            self.add_slicemgr_stat(rspec, "ListResources", result["aggregate"], result["elapsed"], 
                                   result["status"], result.get("exc_info",None))
            if result["status"]=="success":
                res = result['result']['value']
                try:
                    rspec.version.merge(ReturnValue.get_value(res))
                except:
                    api.logger.log_exc("SM.ListResources: Failed to merge aggregate rspec")
    
        # cache the result
        if self.cache and not xrn:
            api.logger.debug("SliceManager.ListResources caches advertisement")
            self.cache.add(version_string, rspec.toxml())
    
        return rspec.toxml()


    def Allocate(self, api, xrn, creds, rspec_str, expiration, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
    
        version_manager = VersionManager()
        def _Allocate(aggregate, server, xrn, credential, rspec, options):
            tStart = time.time()
            try:
                # Need to call GetVersion at an aggregate to determine the supported
                # rspec type/format beofre calling CreateSliver at an Aggregate.
                #server_version = api.get_cached_server_version(server)
                #if 'sfa' not in server_version and 'geni_api' in server_version:
                    # sfa aggregtes support both sfa and pg rspecs, no need to convert
                    # if aggregate supports sfa rspecs. otherwise convert to pg rspec
                    #rspec = RSpec(RSpecConverter.to_pg_rspec(rspec, 'request'))
                    #filter = {'component_manager_id': server_version['urn']}
                    #rspec.filter(filter)
                    #rspec = rspec.toxml()
                result = server.Allocate(xrn, credential, rspec, options)
                return {"aggregate": aggregate, "result": result, "elapsed": time.time()-tStart, "status": "success"}
            except:
                logger.log_exc('Something wrong in _Allocate with URL %s'%server.url)
                return {"aggregate": aggregate, "elapsed": time.time()-tStart, "status": "exception", "exc_info": sys.exc_info()}

        # Validate the RSpec against PlanetLab's schema --disabled for now
        # The schema used here needs to aggregate the PL and VINI schemas
        # schema = "/var/www/html/schemas/pl.rng"
        rspec = RSpec(rspec_str)
    #    schema = None
    #    if schema:
    #        rspec.validate(schema)
    
        # if there is a <statistics> section, the aggregates don't care about it,
        # so delete it.
        self.drop_slicemgr_stats(rspec)
    
        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
    
        # get the callers hrn
        hrn, type = urn_to_hrn(xrn)
        valid_cred = api.auth.checkCredentials(creds, 'createsliver', hrn)[0]
        caller_hrn = Credential(cred=valid_cred).get_gid_caller().get_hrn()
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM 
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            # Just send entire RSpec to each aggregate
            multiclient.run(_Allocate, aggregate, server, xrn, [cred], rspec.toxml(), options)
                
        results = multiclient.get_results()
        manifest_version = version_manager._get_version(rspec.version.type, rspec.version.version, 'manifest')
        result_rspec = RSpec(version=manifest_version)
        geni_urn = None
        geni_slivers = []

        for result in results:
            self.add_slicemgr_stat(result_rspec, "Allocate", result["aggregate"], result["elapsed"], 
                                   result["status"], result.get("exc_info",None))
            if result["status"]=="success":
                try:
                    res = result['result']['value']
                    geni_urn = res['geni_urn']
                    result_rspec.version.merge(ReturnValue.get_value(res['geni_rspec']))
                    geni_slivers.extend(res['geni_slivers'])
                except:
                    api.logger.log_exc("SM.Allocate: Failed to merge aggregate rspec")
        return {
            'geni_urn': geni_urn,
            'geni_rspec': result_rspec.toxml(),
            'geni_slivers': geni_slivers
        }


    def Provision(self, api, xrn, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""

        version_manager = VersionManager()
        def _Provision(aggregate, server, xrn, credential, options):
            tStart = time.time()
            try:
                # Need to call GetVersion at an aggregate to determine the supported
                # rspec type/format beofre calling CreateSliver at an Aggregate.
                server_version = api.get_cached_server_version(server)
                result = server.Provision(xrn, credential, options)
                return {"aggregate": aggregate, "result": result, "elapsed": time.time()-tStart, "status": "success"}
            except:
                logger.log_exc('Something wrong in _Allocate with URL %s'%server.url)
                return {"aggregate": aggregate, "elapsed": time.time()-tStart, "status": "exception", "exc_info": sys.exc_info()}

        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()

        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'createsliver', xrn)[0]
        caller_hrn = Credential(cred=valid_cred).get_gid_caller().get_hrn()
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            # Just send entire RSpec to each aggregate
            multiclient.run(_Provision, aggregate, server, xrn, [cred], options)

        results = multiclient.get_results()
        manifest_version = version_manager._get_version('GENI', '3', 'manifest')
        result_rspec = RSpec(version=manifest_version)
        geni_slivers = []
        geni_urn  = None  
        for result in results:
            self.add_slicemgr_stat(result_rspec, "Provision", result["aggregate"], result["elapsed"],
                                   result["status"], result.get("exc_info",None))
            if result["status"]=="success":
                try:
                    res = result['result']['value']
                    geni_urn = res['geni_urn']
                    result_rspec.version.merge(ReturnValue.get_value(res['geni_rspec']))
                    geni_slivers.extend(res['geni_slivers'])
                except:
                    api.logger.log_exc("SM.Provision: Failed to merge aggregate rspec")
        return {
            'geni_urn': geni_urn,
            'geni_rspec': result_rspec.toxml(),
            'geni_slivers': geni_slivers
        }            


    
    def Renew(self, api, xrn, creds, expiration_time, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True

        def _Renew(aggregate, server, xrn, creds, expiration_time, options):
            try:
                result=server.Renew(xrn, creds, expiration_time, options)
                if type(result)!=dict:
                    result = {'code': {'geni_code': 0}, 'value': result}
                result['aggregate'] = aggregate
                return result
            except:
                logger.log_exc('Something wrong in _Renew with URL %s'%server.url)
                return {'aggregate': aggregate, 'exc_info': traceback.format_exc(),
                        'code': {'geni_code': -1},
                        'value': False, 'output': ""}

        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'renewsliver', xrn)[0]
        caller_hrn = Credential(cred=valid_cred).get_gid_caller().get_hrn()

        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential(minimumExpiration=31*86400)
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            multiclient.run(_Renew, aggregate, server, xrn, [cred], expiration_time, options)

        results = multiclient.get_results()

        geni_code = 0
        geni_output = ",".join([x.get('output',"") for x in results])
        geni_value = reduce (lambda x,y: x and y, [result.get('value',False) for result in results], True)
        for agg_result in results:
            agg_geni_code = agg_result['code'].get('geni_code',0)
            if agg_geni_code:
                geni_code = agg_geni_code

        results = {'aggregates': results, 'code': {'geni_code': geni_code}, 'value': geni_value, 'output': geni_output}

        return results

    def Delete(self, api, xrn, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""

        def _Delete(server, xrn, creds, options):
            return server.Delete(xrn, creds, options)

        (hrn, type) = urn_to_hrn(xrn[0])
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'deletesliver', hrn)[0]
        caller_hrn = Credential(cred=valid_cred).get_gid_caller().get_hrn()

        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            multiclient.run(_Delete, server, xrn, [cred], options)
        
        results = []
        for result in multiclient.get_results():
            results += ReturnValue.get_value(result)
        return results
    
    
    # first draft at a merging SliverStatus
    def Status(self, api, slice_xrn, creds, options):
        def _Status(server, xrn, creds, options):
            return server.Status(xrn, creds, options)

        call_id = options.get('call_id') 
        if Callids().already_handled(call_id): return {}
        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            multiclient.run (_Status, server, slice_xrn, [cred], options)
        results = [ReturnValue.get_value(result) for result in multiclient.get_results()]
    
        # get rid of any void result - e.g. when call_id was hit, where by convention we return {}
        results = [ result for result in results if result and result['geni_slivers']]
    
        # do not try to combine if there's no result
        if not results : return {}
    
        # otherwise let's merge stuff
        geni_slivers = []
        geni_urn  = None
        for result in results:
            try:
                geni_urn = result['geni_urn']
                geni_slivers.extend(result['geni_slivers'])
            except:
                api.logger.log_exc("SM.Provision: Failed to merge aggregate rspec")
        return {
            'geni_urn': geni_urn,
            'geni_slivers': geni_slivers
        }

   
    def Describe(self, api, creds, xrns, options):
        def _Describe(server, xrn, creds, options):
            return server.Describe(xrn, creds, options)

        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return {}
        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            multiclient.run (_Describe, server, xrns, [cred], options)
        results = [ReturnValue.get_value(result) for result in multiclient.get_results()]

        # get rid of any void result - e.g. when call_id was hit, where by convention we return {}
        results = [ result for result in results if result and result.get('geni_urn')]

        # do not try to combine if there's no result
        if not results : return {}

        # otherwise let's merge stuff
        version_manager = VersionManager()
        manifest_version = version_manager._get_version('GENI', '3', 'manifest')
        result_rspec = RSpec(version=manifest_version)
        geni_slivers = []
        geni_urn  = None
        for result in results:
            try:
                geni_urn = result['geni_urn']
                result_rspec.version.merge(ReturnValue.get_value(result['geni_rspec']))
                geni_slivers.extend(result['geni_slivers'])
            except:
                api.logger.log_exc("SM.Provision: Failed to merge aggregate rspec")
        return {
            'geni_urn': geni_urn,
            'geni_rspec': result_rspec.toxml(),    
            'geni_slivers': geni_slivers
        }  
    
    def PerformOperationalAction(self, api, xrn, creds, action, options):
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'createsliver', xrn)[0]
        caller_hrn = Credential(cred=valid_cred).get_gid_caller().get_hrn()
    
        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)    
            multiclient.run(server.PerformOperationalAction, xrn, [cred], action, options)
        multiclient.get_results()    
        return 1
     
    def Shutdown(self, api, xrn, creds, options=None):
        if options is None: options={}
        xrn = Xrn(xrn)  
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'stopslice', xrn.hrn)[0]
        caller_hrn = Credential(cred=valid_cred).get_gid_caller().get_hrn()
    
        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
        multiclient = MultiClient()
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            multiclient.run(server.Shutdown, xrn.urn, cred)
        multiclient.get_results()    
        return 1
    
