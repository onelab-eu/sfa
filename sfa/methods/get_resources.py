### $Id$
### $URL$

from sfa.util.faults import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.ListResources import ListResources 
# RSpecManager_pl is not used. This line is a check that ensures that everything is in place for the import to work.
import sfa.rspecs.aggregates.rspec_manager_pl

class get_resources(ListResources):
    """
    Deprecated. Use ListResources instead. 

    Get an resource specification (rspec). The rspec may describe the resources
    available at an authority or the resources being used by a slice.      

    @param cred credential string specifying the rights of the caller
    @param hrn human readable name of the slice we are interesed in or None 
           for an authority.  
    """

    interfaces = ['aggregate', 'slicemgr']
    
    accepts = [
        Parameter(str, "Credential string"),
        Mixed(Parameter(str, "Human readable name (hrn or urn)"),
              Parameter(None, "hrn not specified")),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(str, "String representatin of an rspec")
    
    def call(self, cred, xrn=None, origin_hrn=None):
        options = {'geni_slice_urn': xrn,
                   'origin_hrn': origin_hrn
        }
                  
        return ListResources.call(self, cred, options)
