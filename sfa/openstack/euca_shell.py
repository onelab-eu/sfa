try:
    import boto
    from boto.ec2.regioninfo import RegionInfo
    from boto.exception import EC2ResponseError
    has_boto=True
except:
    has_boto=False    

from sfa.util.sfalogging import logger
from sfa.openstack.nova_shell import NovaShell
from sfa.util.config import Config

class EucaShell:
    """
    A xmlrpc connection to the euca api. 
    """    

    def __init__(self, config):
        self.config = config

    def get_euca_connection(self):
        if not has_boto:
            logger.info('Unable to access EC2 API - boto library not found.')
            return None
        nova = NovaShell(self.config)
        admin_user = nova.auth_manager.get_user(self.config.SFA_NOVA_USER)
        #access_key = admin_user.access
        access_key = '%s' % admin_user.name
        secret_key = admin_user.secret
        url = self.config.SFA_NOVA_API_URL
        host = None
        port = None    
        path = "/"
        use_ssl = False
        # Split the url into parts 
        if url.find('https://') >= 0:
            use_ssl  = True
            url = url.replace('https://', '')
        elif url.find('http://') >= 0:
            use_ssl  = False
            url = url.replace('http://', '')
        parts = url.split(':')
        host = parts[0]
        if len(parts) > 1:
            parts = parts[1].split('/')
            port = int(parts[0])
            parts = parts[1:]
            path = '/'+'/'.join(parts)
        return boto.connect_ec2(aws_access_key_id=access_key,
                                aws_secret_access_key=secret_key,
                                is_secure=use_ssl,
                                region=RegionInfo(None, 'eucalyptus', host),
                                host=host,
                                port=port,
                                path=path) 

    def __getattr__(self, name):
        def func(*args, **kwds):
            conn = self.get_euca_connection()

