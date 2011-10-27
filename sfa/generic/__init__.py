from sfa.util.sfalogging import logger
from sfa.util.config import Config

from sfa.managers.managerwrapper import ManagerWrapper

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

    def __init__ (self, flavour, config):
        self.flavour=flavour
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
            return getattr(module, classname)(flavour,config)
        except:
            logger.log_exc("Cannot locate generic instance with flavour=%s"%flavour)

    # in the simplest case these can be redefined to the class/module objects to be used
    # see pl.py for an example
    # some descendant of SfaApi
    def api_class (self) : pass
    # in practical terms these are modules for now
    def registry_class (self) : pass
    def slicemgr_class (self) : pass
    def aggregate_class (self) : pass
    def component_class (self) : pass


    # build an API object
    # insert a manager instance 
    def make_api (self, *args, **kwargs):
        # interface is a required arg
        if not 'interface' in kwargs:
            logger.fatal("Generic.make_api: no interface found")
        api = self.api_class()(*args, **kwargs)
        interface=kwargs['interface']
        # or simpler, interface=api.interface
        manager = self.make_manager(interface)
        api.manager = ManagerWrapper(manager,interface)
        return api

    def make_manager (self, interface):
        """
        interface expected in ['registry', 'aggregate', 'slice', 'component']
        flavour is e.g. 'pl' or 'max' or whatever
        """
        flavour = self.flavour
        message="Generic.make_manager for interface=%s and flavour=%s"%(interface,flavour)
        
        classname = "%s_class"%interface
        try:
            module = getattr(self,classname)()
            logger.info("%s : %s"%(message,module))
            return module
        except:
            logger.log_exc(message)
            logger.fatal("Aborting")
        
# former logic was
#        basepath = 'sfa.managers'
#        qualified = "%s.%s_manager_%s"%(basepath,interface,flavour)
#        generic = "%s.%s_manager"%(basepath,interface)
#
#        try: 
#            manager = __import__(qualified, fromlist=[basepath])
#            logger.info ("%s: loaded %s"%(message,qualified))
#        except:
#            try:
#                manager = __import__ (generic, fromlist=[basepath])
#                if flavour != 'pl' : 
#                    logger.warn ("%s: using generic with flavour!='pl'"%(message))
#                logger.info("%s: loaded %s"%(message,generic))
#            except:
#                logger.log_exc("%s: unable to import either %s or %s"%(message,qualified,generic))
#                logger.fatal("Aborted")
#        return manager
        
