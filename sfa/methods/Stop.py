from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.trust.credential import Credential
 
class Stop(Method):
    """
    Stop the specified slice      

    @param cred credential string specifying the rights of the caller
    @param xrn human readable name of slice to instantiate (hrn or urn)
    @return 1 is successful, faults otherwise  
    """

    interfaces = ['aggregate', 'slicemgr', 'component']
    
    accepts = [
        Parameter(str, "Human readable name of slice to instantiate (hrn or urn)"),
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")),
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, xrn, creds):
        hrn, type = urn_to_hrn(xrn)
        valid_creds = self.api.auth.checkCredentials(creds, 'stopslice', hrn)

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, hrn, self.name))

        manager = self.api.get_interface_manager() 
        manager.stop_slice(self.api, xrn, creds)
 
        return 1 
