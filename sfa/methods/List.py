### $Id: list.py 16588 2010-01-13 17:53:44Z anil $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/methods/list.py $

from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.record import SfaRecord
from sfa.trust.credential import Credential

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
       
        manager = self.api.get_interface_manager()
        return manager.list(self.api, xrn) 
