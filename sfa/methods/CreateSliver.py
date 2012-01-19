from sfa.util.faults import SfaInvalidArgument, InvalidRSpec
from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.sfatablesRuntime import run_sfatables
from sfa.trust.credential import Credential
from sfa.storage.parameter import Parameter, Mixed
from sfa.rspecs.rspec import RSpec

class CreateSliver(Method):
    """
    Allocate resources to a slice.  This operation is expected to
    start the allocated resources asynchornously after the operation
    has successfully completed.  Callers can check on the status of
    the resources using SliverStatus.

    @param slice_urn (string) URN of slice to allocate to
    @param credentials ([string]) of credentials
    @param rspec (string) rspec to allocate
    
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Parameter(str, "Slice URN"),
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")),
        Parameter(str, "RSpec"),
        Parameter(type([]), "List of user information"),
        Parameter(dict, "options"),
        ]
    returns = Parameter(str, "Allocated RSpec")

    def call(self, slice_xrn, creds, rspec, users, options):
        hrn, type = urn_to_hrn(slice_xrn)

        self.api.logger.info("interface: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, hrn, self.name))

        # Find the valid credentials
        valid_creds = self.api.auth.checkCredentials(creds, 'createsliver', hrn)
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()

        # make sure users info is specified
        if not users:
            msg = "'users' must be specified and cannot be null. You may need to update your client." 
            raise SfaInvalidArgument(name='users', extra=msg)  

        # flter rspec through sfatables
        if self.api.interface in ['aggregate']:
            chain_name = 'INCOMING'
        elif self.api.interface in ['slicemgr']:
            chain_name = 'FORWARD-INCOMING'
        self.api.logger.debug("CreateSliver: sfatables on chain %s"%chain_name)
        rspec = run_sfatables(chain_name, hrn, origin_hrn, rspec)
        slivers = RSpec(rspec).version.get_nodes_with_slivers()
        if not slivers:
            raise InvalidRSpec("Missing <sliver_type> or <sliver> element. Request rspec must explicitly allocate slivers")    
        result = self.api.manager.CreateSliver(self.api, slice_xrn, creds, rspec, users, options)
        return result
