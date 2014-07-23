from sfa.storage.parameter import Parameter
from sfa.trust.credential import Credential
from sfa.util.method import Method

class Shutdown(Method):
    """
    Perform an emergency shut down of a sliver. This operation is intended for administrative use. 
    The sliver is shut down but remains available for further forensics.

    @param slice_urn (string) URN of slice to renew
    @param credentials ([string]) of credentials    
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Parameter(str, "Slice URN"),
        Parameter(type([dict]), "Credentials"),
        ]
    returns = Parameter(bool, "Success or Failure")

    def call(self, xrn, creds):

        valid_creds = self.api.auth.checkCredentials(creds, 'stopslice', xrn,
                                                     check_sliver_callback = self.api.driver.check_sliver_credentials)
        #log the call
        origin_hrn = Credential(cred=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, xrn, self.name))

        return self.api.manager.Shutdown(self.api, xrn, creds)
    
