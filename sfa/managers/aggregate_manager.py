import soctet
from sfa.rspecs.version_manager import VersionManager
from sfa.util.version import version_core
from sfa.util.xrn import Xrn
from sfa.util.callids import Callids
from sfa.util.sfalogging import logger

class AggregateManager:

    def __init__ (self, config): pass
    
    # essentially a union of the core version, the generic version (this code) and
    # whatever the driver needs to expose

    def _rspec_versions(self):
        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict())
        return {
            'testbed':self.testbed_name(),
            'geni_request_rspec_versions': request_rspec_versions,
            'geni_ad_rspec_versions': ad_rspec_versions,
            }

    def get_rspec_version_string(self, rspec_version, options={}):
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
        xrn=Xrn(api.hrn)
        version = version_core()
        version_generic = {
            'testbed': self.driver.testbed_name(),
            'interface':'aggregate',
            'hrn':xrn.get_hrn(),
            'urn':xrn.get_urn(),
            'geni_api': 3,
            'geni_api_versions': {'3': 'http://%s:%s' % (socket.gethostname(), api.config.sfa_aggregate_port)},
            'geni_single_allocation': 0, # Accept operations that act on as subset of slivers in a given state.
            'geni_allocate': 'geni_many',# Multiple slivers can exist and be incrementally added, including those which connect or overlap in some way.
            'geni_best_effort': 'true',
            'geni_credential_types': [{
                'geni_type': 'geni_sfa',
                'geni_version': 3,
            }],
        }
        version.update(version_generic)
        testbed_version = self.driver.aggregate_version()
        version.update(testbed_version)
        return version
    
    def ListSlices(self, api, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return []
        
        # look in cache first
        if self.driver.cache:
            slices = self.driver.cache.get('slices')
            if slices:
                logger.debug("%s.list_slices returns from cache" % (self.driver.__module__))
                return slices

        # call driver
        slices = self.driver.list_slices(creds, options)

        # cache the result
        if self.driver.cache:
            logger.debug ("%s.list_slices stores value in cache" % (self.driver.__module__))
            self.driver.cache.add('slices', instance_urns)

        return self.driver.list_slices (creds, options)

    def ListResources(self, api, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""

        # get the rspec's return format from options
        version_manager = VersionManager()
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        version_string = self.get_rspec_version_string(rspec_version, options)

        # look in cache first
        cached_requested = options.get('cached', True)
        if cached_requested and self.driver.cache and not slice_hrn:
            rspec = self.driver.cache.get(version_string)
            if rspec:
                logger.debug("%s.ListResources returning cached advertisement" % (self.driver.__module__))
                return rspec
       
        rspec = self.driver.list_resources (version, options) 
        if self.driver.cache:
            logger.debug("%s.ListResources stores advertisement in cache" % (self.driver.__module__))
            self.driver.cache.add(version_string, rspec)    
        return rspec
    
    def Describe(self, api, creds, urns, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""

        version_manager = VersionManager()
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        return self.driver.describe(urns, rspec_version, options)
        
    
    def Status (self, api, urns, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return {}
        return self.driver.status (urns, options=options)
   

    def Allocate(self, api, xrn, creds, rspec_string, options):
        """
        Allocate resources as described in a request RSpec argument 
        to a slice with the named URN.
        """
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
        return self.driver.allocate(xrn, creds, rspec_string, options)
 
    def Provision(self, api, xrns, options):
        """
        Create the sliver[s] (slice) at this aggregate.    
        Verify HRN and initialize the slice record in PLC if necessary.
        """
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
        return self.driver.provision(xrns, creds, options)
    
    def Delete(self, api, xrns, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True
        return self.driver.delete_sliver (xrns, options)

    def Renew(self, api, xrns, expiration_time, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True
        return self.driver.renew(xrns, expiration_time, options)
    
    def GetTicket(self, api, xrn, creds, rspec, users, options):
    
        xrn = Xrn(xrn)
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()

        return self.driver.get_ticket (slice_urn, slice_hrn, creds, rspec, options)

