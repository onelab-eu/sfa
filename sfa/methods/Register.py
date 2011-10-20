### $Id: register.py 16477 2010-01-05 16:31:37Z thierry $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/methods/register.py $

from sfa.trust.certificate import Keypair, convert_public_key
from sfa.trust.gid import *
from sfa.util.faults import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.record import SfaRecord
from sfa.trust.auth import Auth
from sfa.trust.gid import create_uuid
from sfa.trust.credential import Credential

class Register(Method):
    """
    Register an object with the registry. In addition to being stored in the
    SFA database, the appropriate records will also be created in the
    PLC databases
    
    @param cred credential string
    @param record_dict dictionary containing record fields
    
    @return gid string representation
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(dict, "Record dictionary containing record fields"),
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")),
        ]

    returns = Parameter(int, "String representation of gid object")
    
    def call(self, record, creds):
        # validate cred    
        valid_creds = self.api.auth.checkCredentials(creds, 'register')
        
        # verify permissions
        hrn = record.get('hrn', '')
        self.api.auth.verify_object_permission(hrn)

        #log the call
        origin_hrn = Credential(string=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, hrn, self.name))
        
        manager = self.api.get_interface_manager()

        return manager.register(self.api, record)
