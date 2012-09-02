from sfa.util.faults import SfaInvalidArgument, InvalidRSpec, SfatablesRejected
from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.sfatablesRuntime import run_sfatables
from sfa.trust.credential import Credential
from sfa.storage.parameter import Parameter, Mixed
from sfa.rspecs.rspec import RSpec

class Allocate(Method):
    """
    Allocate resources as described in a request RSpec argument 
    to a slice with the named URN. On success, one or more slivers 
    are allocated, containing resources satisfying the request, and 
    assigned to the given slice. This method returns a listing and 
    description of the resources reserved for the slice by this 
    operation, in the form of a manifest RSpec. Allocated slivers 
    are held for an aggregate-determined period. Clients must Renew 
    or Provision slivers before the expiration time (given in the 
    return struct), or the aggregate will automatically Delete them.

    @param slice_urn (string) URN of slice to allocate to
    @param credentials (dict) of credentials
    @param rspec (string) rspec to allocate
    
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Parameter(str, "Slice URN"),
        Parameter(dict, "List of credentials"),
        Parameter(str, "RSpec"),
        Parameter(dict, "options"),
        ]
    returns = Parameter(str, "Allocated RSpec")

    def call(self, xrn, creds, rspec, options):
        xrn = Xrn(xrn, type='slice')
        self.api.logger.info("interface: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, xrn.get_hrn(), self.name))

        # Find the valid credentials
        valid_creds = self.api.auth.checkCredentials(creds, 'createsliver', xrn.get_hrn())
        
        # make sure request is not empty
        slivers = RSpec(rspec).version.get_nodes_with_slivers()
        if not slivers:
            raise InvalidRSpec("Missing <sliver_type> or <sliver> element. Request rspec must explicitly allocate slivers")    

        # flter rspec through sfatables
        if self.api.interface in ['aggregate']:
            chain_name = 'INCOMING'
        elif self.api.interface in ['slicemgr']:
            chain_name = 'FORWARD-INCOMING'
        self.api.logger.debug("Allocate: sfatables on chain %s"%chain_name)
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        rspec = run_sfatables(chain_name, xrn.get_hrn(), origin_hrn, rspec)
        slivers = RSpec(rspec).version.get_nodes_with_slivers()
        if not slivers:
            raise SfatablesRejected(slice_xrn)

        result = self.api.manager.Allocate(self.api, xrn.get_urn(), creds, rspec, options)
        return result
