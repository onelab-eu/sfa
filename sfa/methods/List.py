
from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method

from sfa.trust.credential import Credential

from sfa.storage.parameter import Parameter, Mixed
from sfa.storage.record import SfaRecord

class List(Method):
    """
    List the records in an authority. 

    @param cred credential string specifying the rights of the caller
    @param hrn human readable name of authority to list (hrn or urn)
    @return list of record dictionaries         
    """
    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Human readable name (hrn or urn)"),
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")),
        ]

    returns = [SfaRecord]
    
    def call(self, xrn, creds):
        hrn, type = urn_to_hrn(xrn)
        valid_creds = self.api.auth.checkCredentials(creds, 'list')

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, hrn, self.name))
       
        return self.api.manager.List(self.api, xrn) 
