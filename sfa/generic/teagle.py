from sfa.generic.pl import pl

import sfa.managers.aggregate_manager_teagle

class teagle (pl):

# the teagle flavour behaves like pl, except for 
# the aggregate
    def aggregate_manager_class (self) :
        return sfa.managers.aggregate_manager_teagle.AggregateManagerTeagle

# I believe the component stuff is not implemented
    def component_manager_class (self):
        return None
    def component_driver_class (self):
        return None