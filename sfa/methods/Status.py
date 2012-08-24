from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method

from sfa.storage.parameter import Parameter, Mixed

class Status(Method):
    """
    Get the status of a sliver
    
    @param slice_urn (string) URN of slice to allocate to
    
    """
    interfaces = ['aggregate', 'slicemgr', 'component']
    accepts = [
        Parameter([str], "Slice or sliver URNs"),
        Parameter(dict), "credentials")),
        Parameter(dict, "Options")
        ]
    returns = Parameter(dict, "Status details")

    def call(self, xrns, creds, options):
        valid_creds = self.api.auth.checkCredentials(creds, 'sliverstatus', xrns)

        self.api.logger.info("interface: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, xrns, self.name))
        return self.api.manager.Status(self.api, xrns, creds, options)
    
