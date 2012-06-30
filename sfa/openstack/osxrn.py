import re
from sfa.util.xrn import Xrn
from sfa.util.config import Config

def hrn_to_os_slicename(hrn):
    return OSXrn(xrn=hrn, type='slice').get_slicename()

def cleanup_name(name):
    return name.replace(".", "_").replace("+", "_")                

class OSXrn(Xrn):

    def __init__(self, name=None, auth=None, **kwds):
        
        config = Config()
        if name is not None:
            if 'type' in kwds:
                self.type = kwds['type']
            if auth is not None:
                self.hrn='.'.join([auth, cleanup_name(name)]) 
            else:
                self.hrn = config.SFA_INTERFACE_HRN + "." + cleanup_name(name)
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


    def get_slicename(self):
        self._normalize()
        slicename = self.hrn
        slicename = slicename.split(':')[0]
        slicename = re.sub('[\.]', '_', slicename)
        return slicename
        
            
