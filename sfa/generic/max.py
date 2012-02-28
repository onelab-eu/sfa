# an example of how to plugin the max aggregate manager with the flavour model
# might need to be tested
# 
from sfa.generic.pl import pl

class max (pl):

# the max flavour behaves like pl, except for 
# the aggregate
    def aggregate_manager_class (self) :
        import sfa.managers.aggregate_manager_max
        return sfa.managers.aggregate_manager_max.AggregateManagerMax

# I believe the component stuff is not implemented
    def component_manager_class (self):
        return None
    def component_driver_class (self):
        return None


