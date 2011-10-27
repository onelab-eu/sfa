from sfa.util.faults import *
from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.trust.auth import Auth
from sfa.plc.slices import Slices

class reset_slice(Method):
    """
    Reset the specified slice      

    @param cred credential string specifying the rights of the caller
    @param xrn human readable name of slice to instantiate (hrn or urn)
    @return 1 is successful, faults otherwise  
    """

    interfaces = ['aggregate', 'slicemgr', 'component']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(str, "Human readable name of slice to instantiate (hrn or urn)"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, cred, xrn, origin_hrn=None):
        hrn, type = urn_to_hrn(xrn)
        self.api.auth.check(cred, 'resetslice', hrn)
        # send the call to the right manager
        manager_base = 'sfa.managers'
        if self.api.interface in ['component']:
            mgr_type = self.api.config.SFA_CM_TYPE
            manager_module = manager_base + ".component_manager_%s" % mgr_type
            manager = __import__(manager_module, fromlist=[manager_base])
            manager.reset_slice(self.api, xrn)
        elif self.api.interface in ['aggregate']:
            mgr_type = self.api.config.SFA_AGGREGATE_TYPE
            manager_module = manager_base + ".aggregate_manager_%s" % mgr_type
            manager = __import__(manager_module, fromlist=[manager_base])
            manager.reset_slice(self.api, xrn)
        elif self.api.interface in ['slicemgr']:
            mgr_type = self.api.config.SFA_SM_TYPE
            manager_module = manager_base + ".slice_manager_%s" % mgr_type
            manager = __import__(manager_module, fromlist=[manager_base])
            manager.reset_slice(self.api, xrn) 

        return 1 
