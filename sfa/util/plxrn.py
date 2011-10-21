# specialized Xrn class for PlanetLab
import re
from sfa.util.xrn import Xrn

# temporary helper functions to use this module instead of namespace
def hostname_to_hrn (auth, login_base, hostname):
    return PlXrn(auth=auth+'.'+login_base,hostname=hostname).get_hrn()
def hostname_to_urn(auth, login_base, hostname):
    return PlXrn(auth=auth+'.'+login_base,hostname=hostname).get_urn()
def slicename_to_hrn (auth_hrn, slicename):
    return PlXrn(auth=auth_hrn,slicename=slicename).get_hrn()
def email_to_hrn (auth_hrn, email):
    return PlXrn(auth=auth_hrn, email=email).get_hrn()
def hrn_to_pl_slicename (hrn):
    return PlXrn(xrn=hrn,type='slice').pl_slicename()
def hrn_to_pl_login_base (hrn):
    return PlXrn(xrn=hrn,type='slice').pl_login_base()
def hrn_to_pl_authname (hrn):
    return PlXrn(xrn=hrn,type='any').pl_authname()
def xrn_to_hostname(hrn):
    return Xrn.unescape(PlXrn(xrn=hrn, type='node').get_leaf())

class PlXrn (Xrn):

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
            # split at the first _
            parts = slicename.split("_",1)
            self.hrn = ".".join([auth] + parts )
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
    def pl_slicename (self):
        self._normalize()
        leaf = self.leaf
        leaf = re.sub('[^a-zA-Z0-9_]', '', leaf)
        return self.pl_login_base() + '_' + leaf

    #def hrn_to_pl_authname(hrn):
    def pl_authname (self):
        self._normalize()
        return self.authority[-1]

    def interface_name(self):
        self._normalize()
        return self.leaf

    #def hrn_to_pl_login_base(hrn):
    def pl_login_base (self):
        self._normalize()
        base = self.authority[-1]
        
        # Fix up names of GENI Federates
        base = base.lower()
        base = re.sub('\\\[^a-zA-Z0-9]', '', base)

        if len(base) > 20:
            base = base[len(base)-20:]
        
        return base
