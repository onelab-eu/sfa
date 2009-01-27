import os
import sys
import datetime
import time
import xmlrpclib

from geni.util.geniserver import GeniServer
from geni.util.geniclient import *
from geni.util.cert import Keypair, Certificate
from geni.util.trustedroot import TrustedRootList
from geni.util.excep import *
from geni.util.misc import *
from geni.util.config import Config
from geni.util.rspec import Rspec

class Aggregate(GeniServer):

    hrn = None
    nodes_file = None
    nodes_ttl = None
    nodes = []
    whitelist_file = None
    blacklist_file = None    
    policy = {}
    timestamp = None
    threshold = None    
    shell = None
    registry = None
  
    ##
    # Create a new aggregate object.
    #
    # @param ip the ip address to listen on
    # @param port the port to listen on
    # @param key_file private key filename of registry
    # @param cert_file certificate filename containing public key (could be a GID file)     

    def __init__(self, ip, port, key_file, cert_file, config = "/usr/share/geniwrapper/util/geni_config"):
        GeniServer.__init__(self, ip, port, key_file, cert_file)
        self.conf = Config(config)
        basedir = self.conf.GENI_BASE_DIR + os.sep
        server_basedir = basedir + os.sep + "geni" + os.sep
        self.hrn = self.conf.GENI_INTERFACE_HRN
        self.nodes_file = os.sep.join([server_basedir, 'components', self.hrn + '.comp'])
        self.whitelist_file = os.sep.join([server_basedir, 'policy', 'whitelist'])
        self.blacklist_file = os.sep.join([server_basedir, 'policy', 'blacklist'])
        self.timestamp_file = os.sep.join([server_basedir, 'components', self.hrn + '.timestamp']) 
        self.nodes_ttl = 1
        self.nodes = []
        self.policy = {'whitelist': [], 'blacklist': []} 
        self.connectPLC()
        self.connectRegistry()

    def connectRegistry(self):
        """
        Connect to the registry
        """
        pass
    
    def connectPLC(self):
        """
        Connect to the plc api interface. First attempt to impor thte shell, if that fails
        try to connect to the xmlrpc server.
        """
        self.auth = {'Username': self.conf.GENI_PLC_USER,
                     'AuthMethod': 'password',
                     'AuthString': self.conf.GENI_PLC_PASSWORD}

        try:
           # try to import PLC.Shell directly
            sys.path.append(self.conf.GENI_PLC_SHELL_PATH) 
            import PLC.Shell
            self.shell = PLC.Shell.Shell(globals())
            self.shell.AuthCheck()
        except ImportError:
            # connect to plc api via xmlrpc
            plc_host = self.conf.GENI_PLC_HOST
            plc_port = self.conf.GENI_PLC_PORT
            plc_api_path = self.conf.GENI_PLC_API_PATH                 
            url = "https://%(plc_host)s:%(plc_port)s/%(plc_api_path)s/" % locals()
            self.auth = {'Username': self.conf.GENI_PLC_USER,
                 'AuthMethod': 'password',
                 'AuthString': self.conf.GENI_PLC_PASSWORD} 

            self.shell = xmlrpclib.Server(url, verbose = 0, allow_none = True) 
            self.shell.AuthCheck(self.auth) 

    def hostname_to_hrn(self, login_base, hostname):
        """
        Convert hrn to plantelab name.
        """
        genihostname = "_".join(hostname.split("."))
        return ".".join([self.hrn, login_base, genihostname])

    def slicename_to_hrn(self, slicename):
        """
        Convert hrn to planetlab name.
        """
        slicename = slicename.replace("_", ".")
        return ".".join([self.hrn, slicename])

    def refresh_components(self):
        """
        Update the cached list of nodes.
        """
        # resolve component hostnames 
        nodes = self.shell.GetNodes(self.auth, {}, ['hostname', 'site_id'])
    
        # resolve site login_bases
        site_ids = [node['site_id'] for node in nodes]
        sites = self.shell.GetSites(self.auth, site_ids, ['site_id', 'login_base'])
        site_dict = {}
        for site in sites:
            site_dict[site['site_id']] = site['login_base']

        # convert plc names to geni hrn
        self.nodes = [self.hostname_to_hrn(site_dict[node['site_id']], node['hostname']) for node in nodes]

        # apply policy. Do not allow nodes found in blacklist, only allow nodes found in whitelist
        whitelist_policy = lambda node: node in self.policy['whitelist']
        blacklist_policy = lambda node: node not in self.policy['blacklist']

        if self.policy['blacklist']:
            self.nodes = blacklist_policy(self.nodes)
        if self.policy['whitelist']:
            self.nodes = whitelist_policy(self.nodes)
            
        # update timestamp and threshold
        self.timestamp = datetime.datetime.now()
        delta = datetime.timedelta(hours=self.nodes_ttl)
        self.threshold = self.timestamp + delta 
    
        f = open(self.nodes_file, 'w')
        f.write(str(self.nodes))
        f.close()
        f = open(self.timestamp_file, 'w')
        f.write(str(self.threshold))
        f.close()
 
    def load_components(self):
        """
        Read cached list of nodes.
        """
        # Read component list from cached file 
        if os.path.exists(self.nodes_file):
            f = open(self.nodes_file, 'r')
            self.nodes = eval(f.read())
            f.close()
    
        time_format = "%Y-%m-%d %H:%M:%S"
        if os.path.exists(self.timestamp_file):
            f = open(self.timestamp_file, 'r')
            timestamp = str(f.read()).split(".")[0]
            self.timestamp = datetime.datetime.fromtimestamp(time.mktime(time.strptime(timestamp, time_format)))
            delta = datetime.timedelta(hours=self.nodes_ttl)
            self.threshold = self.timestamp + delta
            f.close()    

    def load_policy(self):
        """
        Read the list of blacklisted and whitelisted nodes.
        """
        whitelist = []
        blacklist = []
        if os.path.exists(self.whitelist_file):
            f = open(self.whitelist_file, 'r')
            lines = f.readlines()
            f.close()
        for line in lines:
            line = line.strip().replace(" ", "").replace("\n", "")
            whitelist.extend(line.split(","))
            
    
        if os.path.exists(self.blacklist_file):
            f = open(self.blacklist_file, 'r')
            lines = f.readlines()
            f.close()
        for line in lines:
            line = line.strip().replace(" ", "").replace("\n", "")
            blacklist.extend(line.split(","))

        self.policy['whitelist'] = whitelist
        self.policy['blacklist'] = blacklist

    def get_components(self):
        """
        Return a list of components at this aggregate.
        """
        # Reload components list
        now = datetime.datetime.now()
        #self.load_components()
        if not self.threshold or not self.timestamp or now > self.threshold:
            self.refresh_components()
        elif now < self.threshold and not self.nodes: 
            self.load_components()
        return self.nodes
     
    def get_rspec(self, hrn, type):
        rspec = Rspec()
        rspec['nodespec'] = {'name': self.conf.GENI_INTERFACE_HRN}
        rsepc['nodespec']['nodes'] = []
        if type in ['node']:
            nodes = self.shell.GetNodes(self.auth)
        elif type in ['slice']:
            slicename = hrn_to_pl_slicename(hrn)
            slices = self.shell.GetSlices(self.auth, [slicename])
            node_ids = slices[0]['node_ids']
            nodes = self.shell.GetNodes(self.auth, node_ids) 
            for node in nodes:
                nodespec = {'name': node['hostname'], 'type': 'std'}
        elif type in ['aggregate']:
            pass

        return rspec

    def get_resources(self, slice_hrn):
        """
        Return the current rspec for the specified slice.
        """
        slicename = hrn_to_plcslicename(slice_hrn)
        rspec = self.get_rspec(slicenamem, 'slice')
        
        return rspec
 
    def create_slice(self, slice_hrn, rspec, attributes = []):
        """
        Instantiate the specified slice according to whats defined in the rspec.
        """
        slicename = self.hrn_to_plcslicename(slice_hrn)
        spec = Rspec(rspec)
        nodespecs = spec.getDictsByTagName('NodeSpec')
        nodes = [nodespec['name'] for nodespec in nodespecs]    
        self.shell.AddSliceToNodes(self.auth, slicename, nodes)
        for attribute in attributes:
            type, value, node, nodegroup = attribute['type'], attribute['value'], attribute['node'], attribute['nodegroup']
            shell.AddSliceAttribute(self.auth, slicename, type, value, node, nodegroup)

        # XX contact the registry to get the list of users on this slice and
        # their keys.
        #slice_record = self.registry.resolve(slice_hrn)
        #person_records = slice_record['users']
        # for person in person_record:
        #    email = person['email']
        #    self.shell.AddPersonToSlice(self.auth, email, slicename) 
     

        return 1

    def update_slice(self, slice_hrn, rspec, attributes = []):
        """
        Update the specified slice.
        """
        # Get slice info
        slicename = self.hrn_to_plcslicename(slice_hrn)
        slices = self.shell.GetSlices(self.auth, [slicename], ['node_ids'])
        if not slice:
            raise RecordNotFound(slice_hrn)
        slice = slices[0]

        # find out where this slice is currently running
        nodes = self.shell.GetNodes(self.auth, slice['node_ids'], ['hostname'])
        hostnames = [node['hostname'] for node in nodes]

        # get netspec details
        spec = Rspec(rspec)
        nodespecs = spec.getDictsByTagName('NodeSpec')
        nodes = [nodespec['name'] for nodespec in nodespecs]    
        # remove nodes not in rspec
        delete_nodes = set(hostnames).difference(nodes)
        # add nodes from rspec
        added_nodes = set(nodes).difference(hostnames)
    
        shell.AddSliceToNodes(self.auth, slicename, added_nodes)
        shell.DeleteSliceFromNodes(self.auth, slicename, deleted_nodes)

        for attribute in attributes:
            type, value, node, nodegroup = attribute['type'], attribute['value'], attribute['node'], attribute['nodegroup']
            shell.AddSliceAttribute(self.auth, slicename, type, value, node, nodegroup)
    
        # contact registry to get slice users and add them to the slice
        # slice_record = self.registry.resolve(slice_hrn)
        # persons = slice_record['users']
        
        #for person in persons:
        #    shell.AddPersonToSlice(person['email'], slice_name) 
    def delete_slice_(self, slice_hrn):
        """
        Remove this slice from all components it was previouly associated with and 
        free up the resources it was using.
        """
        slicename = self.hrn_to_plcslicename(slice_hrn)
        slices = shell.GetSlices(self.auth, [slicename])
        if not slice:
            raise RecordNotFound(slice_hrn)
        slice = slices[0]
      
        shell.DeleteSliceFromNodes(self.auth, slicename, slice['node_ids'])
        return 1

    def start_slice(self, slice_hrn):
        """
        Stop the slice at plc.
        """
        slicename = hrn_to_plcslicename(slice_hrn)
        slices = self.shell.GetSlices(self.auth, {'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice_id = slices[0]
        atrribtes = self.shell.GetSliceAttributes({'slice_id': slice_id, 'name': 'enabled'}, ['slice_attribute_id'])
        attribute_id = attreibutes[0] 
        self.shell.UpdateSliceAttribute(self.auth, attribute_id, "1" )
        return 1

    def stop_slice(self, slice_hrn):
        """
        Stop the slice at plc
        """
        slicename = hrn_to_plcslicename(slice_hrn)
        slices = self.shell.GetSlices(self.auth, {'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice_id = slices[0]
        atrribtes = self.shell.GetSliceAttributes({'slice_id': slice_id, 'name': 'enabled'}, ['slice_attribute_id'])
        attribute_id = attreibutes[0]
        self.shell.UpdateSliceAttribute(self.auth, attribute_id, "0")
        return 1


    def reset_slice(self, slice_hrn):
        """
        Reset the slice
        """
        slicename = self.hrn_to_plcslicename(slice_hrn)
        return 1

    def get_policy(self):
        """
        Return this aggregates policy.
        """
    
        return self.policy
        
    

##############################
## Server methods here for now
##############################

    def components(self):
        return self.get_components()

    #def slices(self):
    #    return self.get_slices()

    def resources(self, cred, hrn):
        self.decode_authentication(cred, 'info')
        self.verify_object_belongs_to_me(hrn)

        return self.get_resources(hrn)

    def createSlice(self, cred, hrn, rspec):
        self.decode_authentication(cred, 'embed')
        self.verify_object_belongs_to_me(hrn)
        return self.create_slice(hrn)

    def updateSlice(self, cred, hrn, rspec):
        self.decode_authentication(cred, 'embed')
        self.verify_object_belongs_to_me(hrn)
        return self.update_slice(hrn)    

    def deleteSlice(self, cred, hrn):
        self.decode_authentication(cred, 'embed')
        self.verify_object_belongs_to_me(hrn)
        return self.delete_slice(hrn)

    def startSlice(self, cred, hrn):
        self.decode_authentication(cred, 'control')
        return self.start_slice(hrn)

    def stopSlice(self, cred, hrn):
        self.decode_authentication(cred, 'control')
        return self.stop(hrn)

    def resetSlice(self, cred, hrn):
        self.decode_authentication(cred, 'control')
        return self.reset(hrn)

    def policy(self, cred):
        self.decode_authentication(cred, 'info')
        return self.get_policy()

    def register_functions(self):
        GeniServer.register_functions(self)

        # Aggregate interface methods
        self.server.register_function(self.components)
        #self.server.register_function(self.slices)
        self.server.register_function(self.resources)
        self.server.register_function(self.createSlice)
        self.server.register_function(self.deleteSlice)
        self.server.register_function(self.startSlice)
        self.server.register_function(self.stopSlice)
        self.server.register_function(self.resetSlice)
        self.server.register_function(self.policy)
              
