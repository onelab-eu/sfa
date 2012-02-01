import re
from sfa.util.xrn import Xrn
from sfa.util.config import Config

class OSXrn(Xrn):

    def __init__(self, name=None, type=None, **kwds):
        
        config = Config()
        if name is not None:
            self.type = type
            self.hrn = config.SFA_INTERFACE_HRN + "." + name
            self.hrn_to_urn()
        else:
            Xrn.__init__(self, **kwds)   
         
        self.name = self.get_name() 
    
    def get_name(self):
        self._normalize()
        leaf = self.leaf
        sliver_id_parts = leaf.split(':')
        name = sliver_id_parts[0]
        name = re.sub('[^a-zA-Z0-9_]', '', name)
        return name

    
