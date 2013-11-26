# specialized Xrn class for Dummy TB
import re
from sfa.util.xrn import Xrn

def xrn_to_hostname(xrn):
    """Returns a node's hostname from its xrn.
    :param xrn: The nodes xrn identifier.
    :type xrn: Xrn (from sfa.util.xrn)

    :returns: node's hostname.
    :rtype: string

    """
    return Xrn.unescape(Xrn(xrn=xrn, type='node').get_leaf())


def xrn_object(root_auth, hostname):
    """Creates a valid xrn object from the node's hostname and the authority
    of the SFA server.

    :param hostname: the node's hostname.
    :param root_auth: the SFA root authority.
    :type hostname: string
    :type root_auth: string

    :returns: the iotlab node's xrn
    :rtype: Xrn

    """
    return Xrn('.'.join([root_auth, Xrn.escape(hostname)]), type='node')

# temporary helper functions to use this module instead of namespace
def hostname_to_hrn (auth, hostname):
    return IotlabXrn(auth=auth ,hostname=hostname).get_hrn()
def hostname_to_urn(auth, hostname):
    return IotlabXrn(auth=auth,hostname=hostname).get_urn()
def slicename_to_hrn (auth_hrn, slicename):
    return IotlabXrn(auth=auth_hrn,slicename=slicename).get_hrn()

def hrn_to_iotlab_slicename (hrn):
    return IotlabXrn(xrn=hrn,type='slice').iotlab_slicename()
def hrn_to_iotlab_authname (hrn):
    return IotlabXrn(xrn=hrn,type='any').iotlab_authname()


class IotlabXrn (Xrn):

    @staticmethod
    def site_hrn (auth, testbed_name):
        return '.'.join([auth, testbed_name])

    def __init__ (self, auth=None, hostname=None, login=None, slicename=None,**kwargs):
        #def hostname_to_hrn(auth_hrn, login_base, hostname):
        if hostname is not None:
            self.type ='node'
            # keep only the first part of the DNS name
            # escape the '.' in the hostname
            self.hrn ='.'.join( [auth, Xrn.escape(hostname)] )
            self.hrn_to_urn()

        elif login is not None:
            self.type = 'person'
            self.hrn = '.'.join([auth, login])
            self.hrn_to_urn()
        #def slicename_to_hrn(auth_hrn, slicename):
        elif slicename is not None:
            self.type ='slice'
            slicename = '_'.join([login, "slice"])
            self.hrn = '.'.join([auth, slicename])
            self.hrn_to_urn()
            # split at the first _



        else:
            Xrn.__init__ (self,**kwargs)

    #def hrn_to_pl_slicename(hrn):
    def iotlab_slicename (self):
        self._normalize()
        leaf = self.leaf
        sliver_id_parts = leaf.split(':')
        name = sliver_id_parts[0]
        name = re.sub('[^a-zA-Z0-9_]', '', name)
        return name

    #def hrn_to_pl_authname(hrn):
    def iotlab_authname (self):
        self._normalize()
        return self.authority[-1]

    def iotlab_login_base (self):
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
