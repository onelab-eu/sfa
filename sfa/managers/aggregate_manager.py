import soctet
from sfa.rspecs.version_manager import VersionManager
from sfa.util.version import version_core
from sfa.util.xrn import Xrn
from sfa.util.callids import Callids

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
        return self.driver.list_slices (creds, options)

    def ListResources(self, api, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""

        # get slice's hrn from options
        slice_xrn = options.get('geni_slice_urn', None)
        # pass None if no slice is specified
        if not slice_xrn:
            slice_hrn, slice_urn = None, None
        else:
            xrn = Xrn(slice_xrn)
            slice_urn=xrn.get_urn()
            slice_hrn=xrn.get_hrn()
        return self.driver.list_resources (slice_urn, slice_hrn, creds, options)
    
    def SliverStatus (self, api, xrn, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return {}
    
        xrn = Xrn(xrn,'slice')
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()
        return self.driver.sliver_status (slice_urn, slice_hrn)
    
    def CreateSliver(self, api, xrn, creds, rspec_string, users, options):
        """
        Create the sliver[s] (slice) at this aggregate.    
        Verify HRN and initialize the slice record in PLC if necessary.
        """
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
    
        xrn = Xrn(xrn, 'slice')
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()

        return self.driver.create_sliver (slice_urn, slice_hrn, creds, rspec_string, users, options)
    
    def DeleteSliver(self, api, xrn, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True

        xrn = Xrn(xrn, 'slice')
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()
        return self.driver.delete_sliver (slice_urn, slice_hrn, creds, options)

    def RenewSliver(self, api, xrn, creds, expiration_time, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True
        
        xrn = Xrn(xrn, 'slice')
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()
        return self.driver.renew_sliver (slice_urn, slice_hrn, creds, expiration_time, options)
    
    ### these methods could use an options extension for at least call_id
    def start_slice(self, api, xrn, creds):
        xrn = Xrn(xrn)
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()
        return self.driver.start_slice (slice_urn, slice_hrn, creds)
     
    def stop_slice(self, api, xrn, creds):
        xrn = Xrn(xrn)
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()
        return self.driver.stop_slice (slice_urn, slice_hrn, creds)

    def reset_slice(self, api, xrn):
        xrn = Xrn(xrn)
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()
        return self.driver.reset_slice (slice_urn, slice_hrn)

    def GetTicket(self, api, xrn, creds, rspec, users, options):
    
        xrn = Xrn(xrn)
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()

        return self.driver.get_ticket (slice_urn, slice_hrn, creds, rspec, options)

