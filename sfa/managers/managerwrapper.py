from sfa.util.faults import SfaNotImplemented
from sfa.util.sfalogging import logger

## locate the right manager
def import_manager(kind, type):
    """
    kind expected in ['registry', 'aggregate', 'slice', 'component']
    type is e.g. 'pl' or 'max' or whatever
    """
    basepath = 'sfa.managers'
    qualified = "%s.%s_manager_%s"%(basepath,kind,type)
    generic = "%s.%s_manager"%(basepath,kind)

    message="import_manager for kind=%s and type=%s"%(kind,type)
    try: 
        manager = __import__(qualified, fromlist=[basepath])
        logger.info ("%s: loaded %s"%(message,qualified))
    except:
        try:
            manager = __import__ (generic, fromlist=[basepath])
            if type != 'pl' : 
                logger.warn ("%s: using generic with type!='pl'"%(message))
            logger.info("%s: loaded %s"%(message,generic))
        except:
            manager=None
            logger.log_exc("%s: unable to import either %s or %s"%(message,qualified,generic))
    return manager
    
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
        
