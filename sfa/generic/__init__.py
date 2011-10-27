from sfa.util.sfalogging import logger
from sfa.util.config import Config
import traceback

# a bundle is the combination of 
# (*) an api that reacts on the incoming requests to trigger the API methods
# (*) a manager that implements the function of the service, 
#     either aggregate, registry, or slicemgr
# (*) a driver that controls the underlying testbed
# 
# 
# The Generic class is a utility that uses the configuration to figure out 
# which combination of these pieces need to be put together 
# from config.
# this extra indirection is needed to adapt to the current naming scheme
# where we have 'pl' and 'plc' and components and the like, that does not 
# yet follow a sensible scheme

# needs refinements to cache more efficiently, esp. wrt the config

class Generic:

    def __init__ (self, config):
        self.config=config

    # proof of concept
    # example flavour='pl' -> sfa.generic.pl.pl()
    @staticmethod
    def the_flavour (flavour=None, config=None):
        if config is None: config=Config()
        if flavour is None: flavour=config.SFA_GENERIC_FLAVOUR
        flavour = flavour.lower()
        #mixed = flavour.capitalize()
        module_path="sfa.generic.%s"%flavour
        classname="%s"%flavour
        logger.info("Generic.the_flavour with flavour=%s"%flavour)
        try:
            module = __import__ (module_path, globals(), locals(), [classname])
            return getattr(module, classname)(config)
        except:
            logger.log_exc("Cannot locate generic instance with flavour=%s"%flavour)


    # how to build an API object
    # default is to use api_class but can be redefined
    def make_api (self, *args, **kwds):
        return self.api_class()(*args, **kwds)
