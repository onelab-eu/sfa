from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.trust.auth import Auth
from sfa.trust.gid import GID
from sfa.trust.certificate import Certificate

class get_gid(Method):
    """
    Returns the client's gid if one exists      

    @param cert certificate string 
    @param xrn human readable name (hrn or urn)  
    @param type object type 
    @return client gid  
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Certificate string"),
        Parameter(str, "Human readable name (hrn or urn)"), 
        Parameter(str, "Object type") 
        ]

    returns = Parameter(str, "GID string")
    
    def call(self, cert, xrn, type):
     
        # convert xrn to hrn     
        if type:
            hrn = urn_to_hrn(xrn)[0]
        else:
            hrn, type = urn_to_hrn(xrn)
 
        self.api.auth.verify_object_belongs_to_me(hrn)

        # resolve the record
        manager_base = 'sfa.managers'
        mgr_type = self.api.config.SFA_REGISTRY_TYPE
        manager_module = manager_base + ".registry_manager_%s" % mgr_type
        manager = __import__(manager_module, fromlist=[manager_base])
        records = manager.resolve(self.api, xrn, type, origin_hrn=hrn)
        if not records:
            raise RecordNotFound(hrn)
        record = records[0]

        # make sure client's certificate is the gid's pub key 
        gid = GID(string=record['gid'])
        certificate = Certificate(string=cert) 
        if not certificate.is_pubkey(gid.get_pubkey()):
            raise ConnectionKeyGIDMismatch(gid.get_subject())
        
        return record['gid'] 
        
