### $Id: stop_slice.py 17732 2010-04-19 21:10:45Z tmack $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/methods/stop_slice.py $

from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.trust.auth import Auth
from sfa.trust.credential import Credential
 
class ListSlices(Method):
    """
    List the slices instantiated at this interface       

    @param cred credential string specifying the rights of the caller
    @return 1 is successful, faults otherwise  
    """

    interfaces = ['aggregate', 'slicemgr', 'component']
    
    accepts = [
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")),
        ]

    returns = Parameter(list, "List of slice names")
    
    def call(self, creds):
        valid_creds = self.api.auth.checkCredentials(creds, 'listslices')

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, self.name))

        manager = self.api.get_interface_manager() 
        return manager.get_slices(self.api, valid_creds)
 
