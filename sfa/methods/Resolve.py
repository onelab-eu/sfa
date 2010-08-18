### $Id: resolve.py 17157 2010-02-21 04:19:34Z tmack $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/methods/resolve.py $
import traceback
import types
from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.debug import log
from sfa.trust.credential import Credential
from sfa.util.record import SfaRecord

class Resolve(Method):
    """
    Resolve a record.

    @param cred credential string authorizing the caller
    @param hrn human readable name to resolve (hrn or urn) 
    @return a list of record dictionaries or empty list     
    """

    interfaces = ['registry']
    
    accepts = [
        Mixed(Parameter(str, "Human readable name (hrn or urn)"),
              Parameter(list, "List of Human readable names ([hrn])")),
        Mixed(Parameter(str, "Credential string"),
              Parameter(list, "List of credentials)"))  
        ]

    returns = [SfaRecord]
    
    def call(self, xrns, creds):
        if not isinstance(xrns, types.ListType):
            xrns=[xrns]
        hrns = [urn_to_hrn(xrn)[0] for xrn in xrns]
        
        #find valid credentials
        valid_creds = self.api.auth.checkCredentials(creds, 'resolve')

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, hrns, self.name))
 
        # send the call to the right manager
        manager = self.api.get_interface_manager()
        return manager.resolve(self.api, xrns)


            
