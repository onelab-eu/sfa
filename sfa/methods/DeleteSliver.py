from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.storage.parameter import Parameter, Mixed
from sfa.trust.auth import Auth
from sfa.trust.credential import Credential

class DeleteSliver(Method):
    """
    Remove the slice from all nodes and free the allocated resources        

    @param xrn human readable name of slice to instantiate (hrn or urn)
    @param cred credential string specifying the rights of the caller
    @return 1 is successful, faults otherwise  
    """

    interfaces = ['aggregate', 'slicemgr', 'component']
    
    accepts = [
        Parameter(str, "Human readable name of slice to delete (hrn or urn)"),
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")),
        Parameter(dict, "options"),
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, xrn, creds, options={}):
        (hrn, type) = urn_to_hrn(xrn)
        valid_creds = self.api.auth.checkCredentials(creds, 'deletesliver', hrn)

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, hrn, self.name))

        self.api.manager.DeleteSliver(self.api, xrn, creds, options)
 
        return 1 
