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
        logger.debug("Generic.the_flavour with flavour=%s"%flavour)
        try:
            module = __import__ (module_path, globals(), locals(), [classname])
            return getattr(module, classname)(flavour,config)
        except:
            logger.log_exc("Cannot locate generic instance with flavour=%s"%flavour)

    # provide default for importer_class
    def importer_class (self): 
        return None

    # in the simplest case these can be redefined to the class/module objects to be used
    # see pl.py for an example
    # some descendant of SfaApi
    def api_class (self) : pass
    # the python classes to use to build up the context
    def registry_class (self) : pass
    def slicemgr_class (self) : pass
    def aggregate_class (self) : pass
    def component_class (self) : pass


    # build an API object
    # insert a manager instance 
    def make_api (self, *args, **kwargs):
        # interface is a required arg
        if not 'interface' in kwargs:
            logger.critical("Generic.make_api: no interface found")
        api = self.api_class()(*args, **kwargs)
        # xxx can probably drop support for managers implemented as modules 
        # which makes it a bit awkward
        manager_class_or_module = self.make_manager(api.interface)
        driver = self.make_driver (api)
        ### arrange stuff together
        # add a manager wrapper
        manager_wrap = ManagerWrapper(manager_class_or_module,api.interface,api.config)
        api.manager=manager_wrap
        # add it in api as well; driver.api is set too as part of make_driver
        api.driver=driver
        return api

    def make_manager (self, interface):
        """
        interface expected in ['registry', 'aggregate', 'slicemgr', 'component']
        flavour is e.g. 'pl' or 'max' or whatever
        """
        flavour = self.flavour
        message="Generic.make_manager for interface=%s and flavour=%s"%(interface,flavour)
        
        classname = "%s_manager_class"%interface
        try:
            module_or_class = getattr(self,classname)()
            logger.debug("%s : %s"%(message,module_or_class))
            # this gets passed to ManagerWrapper that will call the class constructor 
            # if it's a class, or use the module as is if it's a module
            # so bottom line is, don't try the constructor here
            return module_or_class
        except:
            logger.log_exc_critical(message)
        
    # need interface to select the right driver
    def make_driver (self, api):
        config=api.config
        interface=api.interface
        flavour = self.flavour
        message="Generic.make_driver for flavour=%s and interface=%s"%(flavour,interface)
        
        if interface == "component":
            classname = "component_driver_class"
        else:
            classname = "driver_class"
        try:
            class_obj = getattr(self,classname)()
            logger.debug("%s : %s"%(message,class_obj))
            return class_obj(api)
        except:
            logger.log_exc_critical(message)
        
