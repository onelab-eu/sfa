import types

from sfa.util.xrn import Xrn, urn_to_hrn
from sfa.util.method import Method

from sfa.trust.credential import Credential

from sfa.storage.parameter import Parameter, Mixed

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

    # xxx used to be [SfaRecord]
    returns = [Parameter(dict, "registry record")]
    
    def call(self, xrns, creds):
        type = None
        if not isinstance(xrns, types.ListType):
            type = Xrn(xrns).get_type()
            xrns=[xrns]
        hrns = [urn_to_hrn(xrn)[0] for xrn in xrns]
        #find valid credentials
        valid_creds = self.api.auth.checkCredentials(creds, 'resolve')

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, hrns, self.name))
 
        # send the call to the right manager
        return self.api.manager.Resolve(self.api, xrns, type)
            
