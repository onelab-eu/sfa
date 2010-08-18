### $Id: get_credential.py 17576 2010-04-05 20:56:15Z tmack $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/methods/get_credential.py $

from sfa.trust.credential import *
from sfa.trust.rights import *
from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.debug import log
from sfa.trust.credential import Credential

class GetCredential(Method):
    """
    Retrive a credential for an object
    If cred == Nonee then the behavior reverts to get_self_credential

    @param hrn human readable name of object (hrn or urn)
    @param cred credential object specifying rights of the caller
    @param type type of object (user | slice | node | authority )

    @return the string representation of a credential object  
    """

    interfaces = ['registry']
    
    accepts = [
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")), 
        Parameter(str, "Human readable name (hrn or urn)"),
        Mixed(Parameter(str, "Record type"),
              Parameter(None, "Type not specified")),
        ]

    returns = Parameter(str, "String representation of a credential object")

    def call(self, creds, xrn, type):
    
        if type:
            hrn = urn_to_hrn(xrn)[0]
        else:
            hrn, type = urn_to_hrn(xrn)

        # check creds
        valid_creds = self.api.auth.checkCredentials(creds, 'getcredential')
        self.api.auth.verify_object_belongs_to_me(hrn)

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, hrn, self.name))	

        manager = self.api.get_interface_manager()
        
        return manager.get_credential(self.api, xrn, type)

