### $Id: remove.py 16497 2010-01-07 03:33:24Z tmack $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/methods/remove.py $

from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.debug import log
from sfa.trust.credential import Credential

class Remove(Method):
    """
    Remove an object from the registry. If the object represents a PLC object,
    then the PLC records will also be removed.
    
    @param cred credential string
    @param type record type
    @param xrn human readable name of record to remove (hrn or urn)

    @return 1 if successful, faults otherwise 
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Human readable name of slice to instantiate (hrn or urn)"),
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")),
        Mixed(Parameter(str, "Record type"),
              Parameter(None, "Type not specified")),
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, xrn, creds, type):
        if not type:
            hrn = urn_to_hrn(xrn)[0]
        else: 
            hrn, type = urn_to_hrn(xrn)
        
        # validate the cred
        valid_creds = self.api.auth.checkCredentials(creds, "remove")
        self.api.auth.verify_object_permission(hrn)

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, hrn, self.name))


        manager = self.api.get_interface_manager()

        return manager.remove(self.api, xrn, type) 
