import socket
from sfa.rspecs.version_manager import VersionManager
from sfa.util.version import version_core
from sfa.util.xrn import Xrn
from sfa.util.callids import Callids
from sfa.util.sfalogging import logger
from sfa.util.faults import SfaInvalidArgument, InvalidRSpecVersion
from sfa.server.api_versions import ApiVersions


class AggregateManager:

    def __init__ (self, config): pass
    
    # essentially a union of the core version, the generic version (this code) and
    # whatever the driver needs to expose

    def rspec_versions(self):
        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict())
        return {
            'geni_request_rspec_versions': request_rspec_versions,
            'geni_ad_rspec_versions': ad_rspec_versions,
            }

    def get_rspec_version_string(self, rspec_version, options=None):
        if options is None: options={}
        version_string = "rspec_%s" % (rspec_version)

        #panos adding the info option to the caching key (can be improved)
        if options.get('info'):
            version_string = version_string + "_"+options.get('info', 'default')

        # Adding the list_leases option to the caching key
        if options.get('list_leases'):
            version_string = version_string + "_"+options.get('list_leases', 'default')

        # Adding geni_available to caching key
        if options.get('geni_available'):
            version_string = version_string + "_" + str(options.get('geni_available'))

        return version_string

    def GetVersion(self, api, options):
        xrn=Xrn(api.hrn, type='authority+am')
        version = version_core()
        cred_types = [{'geni_type': 'geni_sfa', 'geni_version': str(i)} for i in range(4)[-2:]]
        geni_api_versions = ApiVersions().get_versions()
        geni_api_versions['3'] = 'http://%s:%s' % (api.config.sfa_aggregate_host, api.config.sfa_aggregate_port)
        version_generic = {
            'testbed': api.driver.testbed_name(),
            'interface':'aggregate',
            'sfa': 3,
            'hrn':xrn.get_hrn(),
            'urn':xrn.get_urn(),
            'geni_api': 3,
            'geni_api_versions': geni_api_versions,
            'geni_single_allocation': 0, # Accept operations that act on as subset of slivers in a given state.
            'geni_allocate': 'geni_many',# Multiple slivers can exist and be incrementally added, including those which connect or overlap in some way.
            'geni_credential_types': cred_types,
            'geni_handles_speaksfor': True,     # supports 'speaks for' credentials
        }
        version.update(version_generic)
        version.update(self.rspec_versions())
        testbed_version = api.driver.aggregate_version()
        version.update(testbed_version)
        return version
    
    def ListResources(self, api, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""

        # get the rspec's return format from options
        version_manager = VersionManager()
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        version_string = self.get_rspec_version_string(rspec_version, options)

        # look in cache first
        cached_requested = options.get('cached', True)
        if cached_requested and api.driver.cache:
            rspec = api.driver.cache.get(version_string)
            if rspec:
                logger.debug("%s.ListResources returning cached advertisement" % (api.driver.__module__))
                return rspec
       
        rspec = api.driver.list_resources (rspec_version, options) 
        if api.driver.cache:
            logger.debug("%s.ListResources stores advertisement in cache" % (api.driver.__module__))
            api.driver.cache.add(version_string, rspec)    
        return rspec
    
    def Describe(self, api, creds, urns, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""

        version_manager = VersionManager()
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        return api.driver.describe(urns, rspec_version, options)
        
    
    def Status (self, api, urns, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return {}
        return api.driver.status (urns, options=options)
   

    def Allocate(self, api, xrn, creds, rspec_string, expiration, options):
        """
        Allocate resources as described in a request RSpec argument 
        to a slice with the named URN.
        """
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
        return api.driver.allocate(xrn, rspec_string, expiration, options)
 
    def Provision(self, api, xrns, creds, options):
        """
        Create the sliver[s] (slice) at this aggregate.    
        Verify HRN and initialize the slice record in PLC if necessary.
        """
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""

        # make sure geni_rspec_version is specified in options
        if 'geni_rspec_version' not in options:
            msg = 'geni_rspec_version is required and must be set in options struct'
            raise SfaInvalidArgument(msg, 'geni_rspec_version')
        # make sure we support the requested rspec version
        version_manager = VersionManager()
        rspec_version = version_manager.get_version(options['geni_rspec_version']) 
        if not rspec_version:
            raise InvalidRSpecVersion(options['geni_rspec_version'])
                       
        return api.driver.provision(xrns, options)
    
    def Delete(self, api, xrns, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True
        return api.driver.delete(xrns, options)

    def Renew(self, api, xrns, creds, expiration_time, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True

        return api.driver.renew(xrns, expiration_time, options)

    def PerformOperationalAction(self, api, xrns, creds, action, options=None):
        if options is None: options={}
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True
        return api.driver.perform_operational_action(xrns, action, options) 

    def Shutdown(self, api, xrn, creds, options=None):
        if options is None: options={}
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True
        return api.driver.shutdown(xrn, options) 
    
