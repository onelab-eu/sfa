# specialized Xrn class for NITOS
import re
from sfa.util.xrn import Xrn

# temporary helper functions to use this module instead of namespace
def hostname_to_hrn (auth, login_base, hostname):
    return NitosXrn(auth=auth+'.'+login_base,hostname=hostname).get_hrn()
def hostname_to_urn(auth, login_base, hostname):
    return NitosXrn(auth=auth+'.'+login_base,hostname=hostname).get_urn()
def slicename_to_hrn (auth_hrn,site_name,slicename):
    return NitosXrn(auth=auth_hrn+'.'+site_name,slicename=slicename).get_hrn()
# hack to convert nitos user name to hrn
def username_to_hrn (auth_hrn,site_name,username):
    return NitosXrn(auth=auth_hrn+'.'+site_name,slicename=username).get_hrn()
def email_to_hrn (auth_hrn, email):
    return NitosXrn(auth=auth_hrn, email=email).get_hrn()
def hrn_to_nitos_slicename (hrn):
    return NitosXrn(xrn=hrn,type='slice').nitos_slicename()
# removed-dangerous - was used for non-slice objects
#def hrn_to_nitos_login_base (hrn):
#    return NitosXrn(xrn=hrn,type='slice').nitos_login_base()
def hrn_to_nitos_authname (hrn):
    return NitosXrn(xrn=hrn,type='any').nitos_authname()
def xrn_to_hostname(hrn):
    return Xrn.unescape(NitosXrn(xrn=hrn, type='node').get_leaf())

class NitosXrn (Xrn):

    @staticmethod 
    def site_hrn (auth, login_base):
        return '.'.join([auth,login_base])

    def __init__ (self, auth=None, hostname=None, slicename=None, email=None, interface=None, **kwargs):
        #def hostname_to_hrn(auth_hrn, login_base, hostname):
        if hostname is not None:
            self.type='node'
            # keep only the first part of the DNS name
            #self.hrn='.'.join( [auth,hostname.split(".")[0] ] )
            # escape the '.' in the hostname
            self.hrn='.'.join( [auth,Xrn.escape(hostname)] )
            self.hrn_to_urn()
        #def slicename_to_hrn(auth_hrn, slicename):
        elif slicename is not None:
            self.type='slice'
            self.hrn = ".".join([auth] + [slicename.replace(".", "_")])
            self.hrn_to_urn()
        #def email_to_hrn(auth_hrn, email):
        elif email is not None:
            self.type='person'
            # keep only the part before '@' and replace special chars into _
            self.hrn='.'.join([auth,email.split('@')[0].replace(".", "_").replace("+", "_")])
            self.hrn_to_urn()
        elif interface is not None:
            self.type = 'interface'
            self.hrn = auth + '.' + interface
            self.hrn_to_urn()
        else:
            Xrn.__init__ (self,**kwargs)

    #def hrn_to_pl_slicename(hrn):
    def nitos_slicename (self):
        self._normalize()
        leaf = self.leaf
        sliver_id_parts = leaf.split(':')
        name = sliver_id_parts[0]
        name = re.sub('[^a-zA-Z0-9_]', '', name)
        #return self.nitos_login_base() + '_' + name
        return name

    #def hrn_to_pl_authname(hrn):
    def nitos_authname (self):
        self._normalize()
        return self.authority[-1]

    def interface_name(self):
        self._normalize()
        return self.leaf

    def nitos_login_base (self):
        self._normalize()
        if self.type and self.type.startswith('authority'):
            base = self.leaf 
        else:
            base = self.authority[-1]
        
        # Fix up names of GENI Federates
        base = base.lower()
        base = re.sub('\\\[^a-zA-Z0-9]', '', base)

        if len(base) > 20:
            base = base[len(base)-20:]
        
        return base


if __name__ == '__main__':

        #nitosxrn = NitosXrn(auth="omf.nitos",slicename="aminesl")
        #slice_hrn = nitosxrn.get_hrn()
        #slice_name = NitosXrn(xrn="omf.nitos.aminesl",type='slice').nitos_slicename()
        slicename = "giorgos_n"
        hrn = slicename_to_hrn("pla", "nitos", slicename)
        print hrn  
