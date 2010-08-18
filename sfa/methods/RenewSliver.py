from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter
from sfa.trust.credential import Credential
from dateutil.parser import parse

class RenewSliver(Method):
    """
    Renews the resources in a sliver, extending the lifetime of the slice.    
    @param slice_urn (string) URN of slice to renew
    @param credentials ([string]) of credentials
    @param expiration_time (string) requested time of expiration
    
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Parameter(str, "Slice URN"),
        Parameter(type([str]), "List of credentials"),
        Parameter(str, "Expiration time in RFC 3339 format")
        ]
    returns = Parameter(bool, "Success or Failure")

    def call(self, slice_xrn, creds, expiration_time):
        hrn, type = urn_to_hrn(slice_xrn)

        self.api.logger.info("interface: %s\ttarget-hrn: %s\tcaller-creds: %s\tmethod-name: %s"%(self.api.interface, hrn, creds, self.name))

        # Find the valid credentials
        valid_creds = self.api.auth.checkCredentials(creds, 'renewsliver', hrn)

        # Validate that the time does not go beyond the credential's expiration time
        requested_time = parse(expiration_time)
        if requested_time > Credential(string=valid_creds[0]).get_lifetime():
            raise InsufficientRights('SliverStatus: Credential expires before requested expiration time')
       
        manager = self.api.get_interface_manager()
        manager.renew_slice(self.api, xrn, valid_creds, requested_time)    
 
        return 1
    
