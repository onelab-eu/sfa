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

from sfa.server.threadmanager import ThreadManager

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
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict())
        xrn=Xrn(api.hrn, 'authority+sa')
        version_more = {
            'interface':'slicemgr',
            'sfa': 2,
            'geni_api': 2,
            'geni_api_versions': {'2': 'http://%s:%s' % (api.config.SFA_SM_HOST, api.config.SFA_SM_PORT)},
            'hrn' : xrn.get_hrn(),
            'urn' : xrn.get_urn(),
            'peers': peers,
            'geni_request_rspec_versions': request_rspec_versions,
            'geni_ad_rspec_versions': ad_rspec_versions,
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
                if 'sfa' in version.keys():
                    forward_options['rspec_version'] = version_manager.get_version('SFA 1').to_dict()
                else:
                    forward_options['rspec_version'] = version_manager.get_version('ProtoGENI 2').to_dict()
                    forward_options['geni_rspec_version'] = {'type': 'geni', 'version': '3.0'}
                rspec = server.ListResources(credential, forward_options)
                return {"aggregate": aggregate, "rspec": rspec, "elapsed": time.time()-tStart, "status": "success"}
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
        if not xrn and self.cache and cached_request:
            rspec =  self.cache.get(version_string)
            if rspec:
                api.logger.debug("SliceManager.ListResources returns cached advertisement")
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
            server = api.server_proxy(interface, cred)
            threads.run(_ListResources, aggregate, server, [cred], options)
    
    
        results = threads.get_results()
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
                try:
                    rspec.version.merge(ReturnValue.get_value(result["rspec"]))
                except:
                    api.logger.log_exc("SM.ListResources: Failed to merge aggregate rspec")
    
        # cache the result
        if self.cache and not xrn:
            api.logger.debug("SliceManager.ListResources caches advertisement")
            self.cache.add(version_string, rspec.toxml())
    
        return rspec.toxml()


    def CreateSliver(self, api, xrn, creds, rspec_str, users, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
    
        version_manager = VersionManager()
        def _CreateSliver(aggregate, server, xrn, credential, rspec, users, options):
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
                rspec = server.CreateSliver(xrn, credential, rspec, requested_users, options)
                return {"aggregate": aggregate, "rspec": rspec, "elapsed": time.time()-tStart, "status": "success"}
            except:
                logger.log_exc('Something wrong in _CreateSliver with URL %s'%server.url)
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
        caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()
        threads = ThreadManager()
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM 
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            # Just send entire RSpec to each aggregate
            threads.run(_CreateSliver, aggregate, server, xrn, [cred], rspec.toxml(), users, options)
                
        results = threads.get_results()
        manifest_version = version_manager._get_version(rspec.version.type, rspec.version.version, 'manifest')
        result_rspec = RSpec(version=manifest_version)
        for result in results:
            self.add_slicemgr_stat(result_rspec, "CreateSliver", result["aggregate"], result["elapsed"], 
                                   result["status"], result.get("exc_info",None))
            if result["status"]=="success":
                try:
                    result_rspec.version.merge(ReturnValue.get_value(result["rspec"]))
                except:
                    api.logger.log_exc("SM.CreateSliver: Failed to merge aggregate rspec")
        return result_rspec.toxml()
    
    def RenewSliver(self, api, xrn, creds, expiration_time, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True

        def _RenewSliver(server, xrn, creds, expiration_time, options):
            return server.RenewSliver(xrn, creds, expiration_time, options)
    
        (hrn, type) = urn_to_hrn(xrn)
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'renewsliver', hrn)[0]
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
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            threads.run(_RenewSliver, server, xrn, [cred], expiration_time, options)
        # 'and' the results
        results = [ReturnValue.get_value(result) for result in threads.get_results()]
        return reduce (lambda x,y: x and y, results , True)
    
    def DeleteSliver(self, api, xrn, creds, options):
        call_id = options.get('call_id') 
        if Callids().already_handled(call_id): return ""

        def _DeleteSliver(server, xrn, creds, options):
            return server.DeleteSliver(xrn, creds, options)

        (hrn, type) = urn_to_hrn(xrn)
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'deletesliver', hrn)[0]
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
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            threads.run(_DeleteSliver, server, xrn, [cred], options)
        threads.get_results()
        return 1
    
    
    # first draft at a merging SliverStatus
    def SliverStatus(self, api, slice_xrn, creds, options):
        def _SliverStatus(server, xrn, creds, options):
            return server.SliverStatus(xrn, creds, options)

        call_id = options.get('call_id') 
        if Callids().already_handled(call_id): return {}
        # attempt to use delegated credential first
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
        threads = ThreadManager()
        for aggregate in api.aggregates:
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            threads.run (_SliverStatus, server, slice_xrn, [cred], options)
        results = [ReturnValue.get_value(result) for result in threads.get_results()]
    
        # get rid of any void result - e.g. when call_id was hit, where by convention we return {}
        results = [ result for result in results if result and result['geni_resources']]
    
        # do not try to combine if there's no result
        if not results : return {}
    
        # otherwise let's merge stuff
        overall = {}
    
        # mmh, it is expected that all results carry the same urn
        overall['geni_urn'] = results[0]['geni_urn']
        overall['pl_login'] = results[0]['pl_login']
        # append all geni_resources
        overall['geni_resources'] = \
            reduce (lambda x,y: x+y, [ result['geni_resources'] for result in results] , [])
        overall['status'] = 'unknown'
        if overall['geni_resources']:
            overall['status'] = 'ready'
    
        return overall
    
    def ListSlices(self, api, creds, options):
        call_id = options.get('call_id') 
        if Callids().already_handled(call_id): return []
    
        def _ListSlices(server, creds, options):
            return server.ListSlices(creds, options)

        # look in cache first
        # xxx is this really frequent enough that it is worth being cached ?
        if self.cache:
            slices = self.cache.get('slices')
            if slices:
                api.logger.debug("SliceManager.ListSlices returns from cache")
                return slices
    
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'listslices', None)[0]
        caller_hrn = Credential(string=valid_cred).get_gid_caller().get_hrn()
    
        # attempt to use delegated credential first
        cred= api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential()
        threads = ThreadManager()
        # fetch from aggregates
        for aggregate in api.aggregates:
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            threads.run(_ListSlices, server, [cred], options)
    
        # combime results
        results = [ReturnValue.get_value(result) for result in threads.get_results()]
        slices = []
        for result in results:
            slices.extend(result)
    
        # cache the result
        if self.cache:
            api.logger.debug("SliceManager.ListSlices caches value")
            self.cache.add('slices', slices)
    
        return slices
    
    
    def GetTicket(self, api, xrn, creds, rspec, users, options):
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
        cred = api.getDelegatedCredential(creds)
        if not cred:
            cred = api.getCredential() 
        threads = ThreadManager()
        for (aggregate, aggregate_rspec) in aggregate_rspecs.iteritems():
            # xxx sounds like using call_id here would be safer
            # prevent infinite loop. Dont send request back to caller
            # unless the caller is the aggregate's SM
            if caller_hrn == aggregate and aggregate != api.hrn:
                continue
            
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            threads.run(server.GetTicket, xrn, [cred], aggregate_rspec, users, options)
    
        results = threads.get_results()
        
        # gather information from each ticket 
        rspec = None
        initscripts = []
        slivers = [] 
        object_gid = None  
        for result in results:
            agg_ticket = SfaTicket(string=result)
            attrs = agg_ticket.get_attributes()
            if not object_gid:
                object_gid = agg_ticket.get_gid_object()
            if not rspec:
                rspec = RSpec(agg_ticket.get_rspec())
            else:
                rspec.version.merge(agg_ticket.get_rspec())
            initscripts.extend(attrs.get('initscripts', [])) 
            slivers.extend(attrs.get('slivers', [])) 
        
        # merge info
        attributes = {'initscripts': initscripts,
                     'slivers': slivers}
        
        # create a new ticket
        ticket = SfaTicket(subject = slice_hrn)
        ticket.set_gid_caller(api.auth.client_gid)
        ticket.set_issuer(key=api.key, subject=api.hrn)
        ticket.set_gid_object(object_gid)
        ticket.set_pubkey(object_gid.get_pubkey())
        #new_ticket.set_parent(api.auth.hierarchy.get_auth_ticket(auth_hrn))
        ticket.set_attributes(attributes)
        ticket.set_rspec(rspec.toxml())
        ticket.encode()
        ticket.sign()          
        return ticket.save_to_string(save_parents=True)
    
    def start_slice(self, api, xrn, creds):
        hrn, type = urn_to_hrn(xrn)
    
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'startslice', hrn)[0]
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
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)    
            threads.run(server.Start, xrn, cred)
        threads.get_results()    
        return 1
     
    def stop_slice(self, api, xrn, creds):
        hrn, type = urn_to_hrn(xrn)
    
        # get the callers hrn
        valid_cred = api.auth.checkCredentials(creds, 'stopslice', hrn)[0]
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
            interface = api.aggregates[aggregate]
            server = api.server_proxy(interface, cred)
            threads.run(server.Stop, xrn, cred)
        threads.get_results()    
        return 1
    
    def reset_slice(self, api, xrn):
        """
        Not implemented
        """
        return 1
    
    def shutdown(self, api, xrn, creds):
        """
        Not implemented   
        """
        return 1
    
    def status(self, api, xrn, creds):
        """
        Not implemented 
        """
        return 1

