import re
from sfa.util.xrn import Xrn
from sfa.util.config import Config

def hrn_to_os_slicename(hrn):
    return OSXrn(xrn=hrn, type='slice').get_slicename()


def hrn_to_os_tenant_name(hrn):
    return OSXrn(xrn=hrn, type='slice').get_tenant_name()

def cleanup_name(name):
    return name.replace(".", "_").replace("+", "_")                

class OSXrn(Xrn):

    def __init__(self, name=None, auth=None, **kwds):
        
        config = Config()
        self.id = id
        if name is not None:
            if 'type' in kwds:
                self.type = kwds['type']
            if auth is not None:
                self.hrn='.'.join([auth, cleanup_name(name)]) 
            else:
                self.hrn = name.replace('_', '.')
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

    def get_tenant_name(self):
        self._normalize()
        tenant_name = self.hrn.replace('\.', '')
        return tenant_name
       
