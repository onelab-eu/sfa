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
        self.nova_shell = NovaShell(config)
        self.access_key = None
        self.secret_key = None

    def init_context(self, project_name=None):
        
        # use the context of the specified  project's project
        # manager. 
        if project_name:
            project = self.nova_shell.auth_manager.get_project(project_name)
            self.access_key = "%s:%s" % (project.project_manager.name, project_name)
            self.secret_key = project.project_manager.secret
        else:
            # use admin user's context
            admin_user = self.nova_shell.auth_manager.get_user(self.config.SFA_NOVA_USER)
            #access_key = admin_user.access
            self.access_key = '%s' % admin_user.name
            self.secret_key = admin_user.secret

    def get_euca_connection(self, project_name=None):
        if not has_boto:
            logger.info('Unable to access EC2 API - boto library not found.')
            return None

        if not self.access_key or not self.secret_key:
            self.init_context(project_name)
        
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
        return boto.connect_ec2(aws_access_key_id=self.access_key,
                                aws_secret_access_key=self.secret_key,
                                is_secure=use_ssl,
                                region=RegionInfo(None, 'eucalyptus', host),
                                host=host,
                                port=port,
                                path=path) 

    def __getattr__(self, name):
        def func(*args, **kwds):
            conn = self.get_euca_connection()

