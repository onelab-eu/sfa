from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.sfatablesRuntime import run_sfatables
import sys
from sfa.trust.credential import Credential
from sfa.util.sfalogging import logger

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
        Parameter(type([]), "List of user information")
        ]
    returns = Parameter(str, "Allocated RSpec")

    def call(self, slice_xrn, creds, rspec, users):
        hrn, type = urn_to_hrn(slice_xrn)

        self.api.logger.info("interface: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, hrn, self.name))

        # Find the valid credentials
        valid_creds = self.api.auth.checkCredentials(creds, 'createsliver', hrn)
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()

        manager = self.api.get_interface_manager()
        
        # flter rspec through sfatables
        if self.api.interface in ['aggregate']:
            chain_name = 'OUTGOING'
        elif self.api.interface in ['slicemgr']:
            chain_name = 'FORWARD-OUTGOING'
        rspec = run_sfatables(chain_name, hrn, origin_hrn, rspec)
        allocated = manager.create_slice(self.api, slice_xrn, creds, rspec, users)

        return rspec 
    
