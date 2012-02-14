import boto
from boto.ec2.regioninfo import RegionInfo
from boto.exception import EC2ResponseError
from sfa.util.sfalogging import logger


class EucaShell:
    """
    A xmlrpc connection to the euca api. 
    """    

    def __init__(self, config):
        self.config = Config

    def get_euca_connection(self):

        access_key = self.config.SFA_EUCA_ACCESS_KEY
        secret_key = self.config.SFA_EUCA_SECRET_KEY
        url = self.config.SFA_EUCA_URL
        path = "/"
        euca_port = self.config.SFA_EUCA_PORT        
        use_ssl = False

        # Split the url into parts 
        if url.find('https://') >= 0:
            use_ssl  = True
            url = url.replace('https://', '')
        elif url.find('http://') >= 0:
            use_ssl  = False
            url = url.replace('http://', '')
        (host, parts) = url.split(':')
        if len(parts) > 1:
            parts = parts.split('/')
            port = int(parts[0])
            parts = parts[1:]
            path = '/'.join(parts)
        
        if not access_key or not secret_key or not url:
            logger.error('Please set ALL of the required environment ' \
                         'variables by sourcing the eucarc file.')
            return None
        return boto.connect_ec2(aws_access_key_id=access_key,
                                aws_secret_access_key=secret_key,
                                is_secure=use_ssl,
                                region=RegionInfo(None, 'eucalyptus', host),
                                port=port,
                                path=path) 

    def __getattr__(self, name):
        def func(*args, **kwds):
            conn = self.get_euca_connection()
            return getattr(conn, name)(*args, **kwds)
        return func                     
