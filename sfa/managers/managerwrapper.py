from sfa.util.faults import SfaNotImplemented
from sfa.util.sfalogging import logger

####################
class ManagerWrapper:
    """
    This class acts as a wrapper around an SFA interface manager module, but
    can be used with any python module. The purpose of this class is raise a 
    SfaNotImplemented exception if someone attempts to use an attribute 
    (could be a callable) thats not available in the library by checking the
    library using hasattr. This helps to communicate better errors messages 
    to the users and developers in the event that a specifiec operation 
    is not implemented by a libarary and will generally be more helpful than
    the standard AttributeError         
    """
    def __init__(self, manager, interface):
        self.manager = manager
        self.interface = interface
        
    def __getattr__(self, method):
        if not hasattr(self.manager, method):
            raise SfaNotImplemented(method, self.interface)
        return getattr(self.manager, method)
        
