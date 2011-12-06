#! /usr/bin/env python

# sfi -- slice-based facility interface

# xxx NOTE this will soon be reviewed to take advantage of sfaclientlib

import sys
sys.path.append('.')

import os, os.path
#import tempfile
import socket
import datetime
import codecs
import pickle
from lxml import etree
from StringIO import StringIO
from optparse import OptionParser

from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.gid import GID
from sfa.trust.credential import Credential
from sfa.trust.sfaticket import SfaTicket

from sfa.util.sfalogging import sfi_logger
from sfa.util.xrn import get_leaf, get_authority, hrn_to_urn
from sfa.util.config import Config
from sfa.util.version import version_core
from sfa.util.cache import Cache

from sfa.storage.record import SfaRecord, UserRecord, SliceRecord, NodeRecord, AuthorityRecord

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.rspec_converter import RSpecConverter
from sfa.rspecs.version_manager import VersionManager
from sfa.client.return_value import ReturnValue

import sfa.client.sfaprotocol as sfaprotocol
from sfa.client.client_helper import pg_users_arg, sfa_users_arg

AGGREGATE_PORT=12346
CM_PORT=12346

# utility methods here
# display methods
def display_rspec(rspec, format='rspec'):
    if format in ['dns']:
        tree = etree.parse(StringIO(rspec))
        root = tree.getroot()
        result = root.xpath("./network/site/node/hostname/text()")
    elif format in ['ip']:
        # The IP address is not yet part of the new RSpec
        # so this doesn't do anything yet.
        tree = etree.parse(StringIO(rspec))
        root = tree.getroot()
        result = root.xpath("./network/site/node/ipv4/text()")
    else:
        result = rspec

    print result
    return

def display_list(results):
    for result in results:
        print result

def display_records(recordList, dump=False):
    ''' Print all fields in the record'''
    for record in recordList:
        display_record(record, dump)

def display_record(record, dump=False):
    if dump:
        record.dump()
    else:
        info = record.getdict()
        print "%s (%s)" % (info['hrn'], info['type'])
    return


def filter_records(type, records):
    filtered_records = []
    for record in records:
        if (record['type'] == type) or (type == "all"):
            filtered_records.append(record)
    return filtered_records


# save methods
def save_variable_to_file(var, filename, format="text"):
    f = open(filename, "w")
    if format == "text":
        f.write(str(var))
    elif format == "pickled":
        f.write(pickle.dumps(var))
    else:
        # this should never happen
        print "unknown output format", format


def save_rspec_to_file(rspec, filename):
    if not filename.endswith(".rspec"):
        filename = filename + ".rspec"
    f = open(filename, 'w')
    f.write(rspec)
    f.close()
    return

def save_records_to_file(filename, recordList, format="xml"):
    if format == "xml":
        index = 0
        for record in recordList:
            if index > 0:
                save_record_to_file(filename + "." + str(index), record)
            else:
                save_record_to_file(filename, record)
            index = index + 1
    elif format == "xmllist":
        f = open(filename, "w")
        f.write("<recordlist>\n")
        for record in recordList:
            record = SfaRecord(dict=record)
            f.write('<record hrn="' + record.get_name() + '" type="' + record.get_type() + '" />\n')
        f.write("</recordlist>\n")
        f.close()
    elif format == "hrnlist":
        f = open(filename, "w")
        for record in recordList:
            record = SfaRecord(dict=record)
            f.write(record.get_name() + "\n")
        f.close()
    else:
        # this should never happen
        print "unknown output format", format

def save_record_to_file(filename, record):
    if record['type'] in ['user']:
        record = UserRecord(dict=record)
    elif record['type'] in ['slice']:
        record = SliceRecord(dict=record)
    elif record['type'] in ['node']:
        record = NodeRecord(dict=record)
    elif record['type'] in ['authority', 'ma', 'sa']:
        record = AuthorityRecord(dict=record)
    else:
        record = SfaRecord(dict=record)
    str = record.save_to_string()
    f=codecs.open(filename, encoding='utf-8',mode="w")
    f.write(str)
    f.close()
    return


# load methods
def load_record_from_file(filename):
    f=codecs.open(filename, encoding="utf-8", mode="r")
    str = f.read()
    f.close()
    record = SfaRecord(string=str)
    return record


import uuid
def unique_call_id(): return uuid.uuid4().urn

class Sfi:
    
    required_options=['verbose',  'debug',  'registry',  'sm',  'auth',  'user']

    @staticmethod
    def default_sfi_dir ():
        if os.path.isfile("./sfi_config"): 
            return os.getcwd()
        else:
            return os.path.expanduser("~/.sfi/")

    # dummy to meet Sfi's expectations for its 'options' field
    # i.e. s/t we can do setattr on
    class DummyOptions:
        pass

    def __init__ (self,options=None):
        if options is None: options=Sfi.DummyOptions()
        for opt in Sfi.required_options:
            if not hasattr(options,opt): setattr(options,opt,None)
        if not hasattr(options,'sfi_dir'): options.sfi_dir=Sfi.default_sfi_dir()
        self.options = options
        self.slicemgr = None
        self.registry = None
        self.user = None
        self.authority = None
        self.hashrequest = False
        self.logger = sfi_logger
        self.logger.enable_console()
   
    def create_cmd_parser(self, command):
        cmdargs = {"list": "authority",
                  "show": "name",
                  "remove": "name",
                  "add": "record",
                  "update": "record",
                  "create_gid": "[name]",
                  "get_gid": [],  
                  "get_trusted_certs": "cred",
                  "slices": "",
                  "resources": "[name]",
                  "create": "name rspec",
                  "get_ticket": "name rspec",
                  "redeem_ticket": "ticket",
                  "delete": "name",
                  "reset": "name",
                  "start": "name",
                  "stop": "name",
                  "delegate": "name",
                  "status": "name",
                  "renew": "name",
                  "shutdown": "name",
                  "version": "",  
                 }

        if command not in cmdargs:
            msg="Invalid command\n"
            msg+="Commands: "
            msg += ','.join(cmdargs.keys())            
            self.logger.critical(msg)
            sys.exit(2)

        parser = OptionParser(usage="sfi [sfi_options] %s [options] %s" \
                                     % (command, cmdargs[command]))

        # user specifies remote aggregate/sm/component                          
        if command in ("resources", "slices", "create", "delete", "start", "stop", 
                       "restart", "shutdown",  "get_ticket", "renew", "status"):
            parser.add_option("-a", "--aggregate", dest="aggregate",
                             default=None, help="aggregate host")
            parser.add_option("-p", "--port", dest="port",
                             default=AGGREGATE_PORT, help="aggregate port")
            parser.add_option("-c", "--component", dest="component", default=None,
                             help="component hrn")
            parser.add_option("-d", "--delegate", dest="delegate", default=None, 
                             action="store_true",
                             help="Include a credential delegated to the user's root"+\
                                  "authority in set of credentials for this call")

        # registy filter option
        if command in ("list", "show", "remove"):
            parser.add_option("-t", "--type", dest="type", type="choice",
                            help="type filter ([all]|user|slice|authority|node|aggregate)",
                            choices=("all", "user", "slice", "authority", "node", "aggregate"),
                            default="all")
        # display formats
        if command in ("resources"):
            parser.add_option("-r", "--rspec-version", dest="rspec_version", default="SFA 1",
                              help="schema type and version of resulting RSpec")
            parser.add_option("-f", "--format", dest="format", type="choice",
                             help="display format ([xml]|dns|ip)", default="xml",
                             choices=("xml", "dns", "ip"))
            #panos: a new option to define the type of information about resources a user is interested in
	    parser.add_option("-i", "--info", dest="info",
                                help="optional component information", default=None)


        # 'create' does return the new rspec, makes sense to save that too
        if command in ("resources", "show", "list", "create_gid", 'create'):
           parser.add_option("-o", "--output", dest="file",
                            help="output XML to file", metavar="FILE", default=None)

        if command in ("show", "list"):
           parser.add_option("-f", "--format", dest="format", type="choice",
                             help="display format ([text]|xml)", default="text",
                             choices=("text", "xml"))

           parser.add_option("-F", "--fileformat", dest="fileformat", type="choice",
                             help="output file format ([xml]|xmllist|hrnlist)", default="xml",
                             choices=("xml", "xmllist", "hrnlist"))

        if command in ("status", "version"):
           parser.add_option("-o", "--output", dest="file",
                            help="output dictionary to file", metavar="FILE", default=None)
           parser.add_option("-F", "--fileformat", dest="fileformat", type="choice",
                             help="output file format ([text]|pickled)", default="text",
                             choices=("text","pickled"))

        if command in ("delegate"):
           parser.add_option("-u", "--user",
                            action="store_true", dest="delegate_user", default=False,
                            help="delegate user credential")
           parser.add_option("-s", "--slice", dest="delegate_slice",
                            help="delegate slice credential", metavar="HRN", default=None)
        
        if command in ("version"):
            parser.add_option("-a", "--aggregate", dest="aggregate",
                             default=None, help="aggregate host")
            parser.add_option("-p", "--port", dest="port",
                             default=AGGREGATE_PORT, help="aggregate port")
            parser.add_option("-R","--registry-version",
                              action="store_true", dest="version_registry", default=False,
                              help="probe registry version instead of slicemgr")
            parser.add_option("-l","--local",
                              action="store_true", dest="version_local", default=False,
                              help="display version of the local client")

        return parser

        
    def create_parser(self):

        # Generate command line parser
        parser = OptionParser(usage="sfi [options] command [command_options] [command_args]",
                             description="Commands: gid,list,show,remove,add,update,nodes,slices,resources,create,delete,start,stop,reset")
        parser.add_option("-r", "--registry", dest="registry",
                         help="root registry", metavar="URL", default=None)
        parser.add_option("-s", "--slicemgr", dest="sm",
                         help="slice manager", metavar="URL", default=None)
        parser.add_option("-d", "--dir", dest="sfi_dir",
                         help="config & working directory - default is " + Sfi.default_sfi_dir(),
                         metavar="PATH", default=Sfi.default_sfi_dir())
        parser.add_option("-u", "--user", dest="user",
                         help="user name", metavar="HRN", default=None)
        parser.add_option("-a", "--auth", dest="auth",
                         help="authority name", metavar="HRN", default=None)
        parser.add_option("-v", "--verbose", action="count", dest="verbose", default=0,
                         help="verbose mode - cumulative")
        parser.add_option("-D", "--debug",
                          action="store_true", dest="debug", default=False,
                          help="Debug (xml-rpc) protocol messages")
        parser.add_option("-p", "--protocol", dest="protocol", default="xmlrpc",
                         help="RPC protocol (xmlrpc or soap)")
        parser.add_option("-k", "--hashrequest",
                         action="store_true", dest="hashrequest", default=False,
                         help="Create a hash of the request that will be authenticated on the server")
        parser.add_option("-t", "--timeout", dest="timeout", default=None,
                         help="Amout of time tom wait before timing out the request")
        parser.disable_interspersed_args()

        return parser
        

    def read_config(self):
       config_file = os.path.join(self.options.sfi_dir,"sfi_config")
       try:
          config = Config (config_file)
       except:
          self.logger.critical("Failed to read configuration file %s"%config_file)
          self.logger.info("Make sure to remove the export clauses and to add quotes")
          if self.options.verbose==0:
              self.logger.info("Re-run with -v for more details")
          else:
              self.logger.log_exc("Could not read config file %s"%config_file)
          sys.exit(1)
    
       errors = 0
       # Set SliceMgr URL
       if (self.options.sm is not None):
          self.sm_url = self.options.sm
       elif hasattr(config, "SFI_SM"):
          self.sm_url = config.SFI_SM
       else:
          self.logger.error("You need to set e.g. SFI_SM='http://your.slicemanager.url:12347/' in %s" % config_file)
          errors += 1 
    
       # Set Registry URL
       if (self.options.registry is not None):
          self.reg_url = self.options.registry
       elif hasattr(config, "SFI_REGISTRY"):
          self.reg_url = config.SFI_REGISTRY
       else:
          self.logger.errors("You need to set e.g. SFI_REGISTRY='http://your.registry.url:12345/' in %s" % config_file)
          errors += 1 
          

       # Set user HRN
       if (self.options.user is not None):
          self.user = self.options.user
       elif hasattr(config, "SFI_USER"):
          self.user = config.SFI_USER
       else:
          self.logger.errors("You need to set e.g. SFI_USER='plc.princeton.username' in %s" % config_file)
          errors += 1 
    
       # Set authority HRN
       if (self.options.auth is not None):
          self.authority = self.options.auth
       elif hasattr(config, "SFI_AUTH"):
          self.authority = config.SFI_AUTH
       else:
          self.logger.error("You need to set e.g. SFI_AUTH='plc.princeton' in %s" % config_file)
          errors += 1 
    
       if errors:
          sys.exit(1)


    #
    # Establish Connection to SliceMgr and Registry Servers
    #
    def set_servers(self):

       self.read_config() 
       # Get key and certificate
       key_file = self.get_key_file()
       cert_file = self.get_cert_file(key_file)
       self.key_file = key_file
       self.cert_file = cert_file
       self.cert = GID(filename=cert_file)
       self.logger.info("Contacting Registry at: %s"%self.reg_url)
       self.registry = sfaprotocol.server_proxy(self.reg_url, key_file, cert_file, timeout=self.options.timeout, verbose=self.options.debug)  
       self.logger.info("Contacting Slice Manager at: %s"%self.sm_url)
       self.slicemgr = sfaprotocol.server_proxy(self.sm_url, key_file, cert_file, timeout=self.options.timeout, verbose=self.options.debug)
       return

    def get_cached_server_version(self, server):
        # check local cache first
        cache = None
        version = None 
        cache_file = os.path.join(self.options.sfi_dir,'sfi_cache.dat')
        cache_key = server.url + "-version"
        try:
            cache = Cache(cache_file)
        except IOError:
            cache = Cache()
            self.logger.info("Local cache not found at: %s" % cache_file)

        if cache:
            version = cache.get(cache_key)

        if not version: 
            result = server.GetVersion()
            version= ReturnValue.get_value(result)
            # cache version for 24 hours
            cache.add(cache_key, version, ttl= 60*60*24)
            self.logger.info("Updating cache file %s" % cache_file)
            cache.save_to_file(cache_file)

        return version   
        

    def server_supports_options_arg(self, server):
        """
        Returns true if server support the optional call_id arg, false otherwise. 
        """
        server_version = self.get_cached_server_version(server)
        if 'sfa' in server_version and 'code_tag' in server_version:
            code_tag = server_version['code_tag']
            code_tag_parts = code_tag.split("-")
            
            version_parts = code_tag_parts[0].split(".")
            major, minor = version_parts[0], version_parts[1]
            rev = code_tag_parts[1]
            if int(major) >= 1:
                if int(minor) >= 2:
                    return True
        return False                
        
    #
    # Get various credential and spec files
    #
    # Establishes limiting conventions
    #   - conflates MAs and SAs
    #   - assumes last token in slice name is unique
    #
    # Bootstraps credentials
    #   - bootstrap user credential from self-signed certificate
    #   - bootstrap authority credential from user credential
    #   - bootstrap slice credential from user credential
    #
    
    
    def get_key_file(self):
       file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".pkey")
       if (os.path.isfile(file)):
          return file
       else:
          self.logger.error("Key file %s does not exist"%file)
          sys.exit(-1)
       return
    
    def get_cert_file(self, key_file):
    
        cert_file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".cert")
        if (os.path.isfile(cert_file)):
            # we'd perfer to use Registry issued certs instead of self signed certs. 
            # if this is a Registry cert (GID) then we are done 
            gid = GID(filename=cert_file)
            if gid.get_urn():
                return cert_file

        # generate self signed certificate
        k = Keypair(filename=key_file)
        cert = Certificate(subject=self.user)
        cert.set_pubkey(k)
        cert.set_issuer(k, self.user)
        cert.sign()
        self.logger.info("Writing self-signed certificate to %s"%cert_file)
        cert.save_to_file(cert_file)
        self.cert = cert
        # try to get registry issued cert
        try:
            self.logger.info("Getting Registry issued cert")
            self.read_config()
            # *hack.  need to set registry before _get_gid() is called 
            self.registry = sfaprotocol.server_proxy(self.reg_url, key_file, cert_file, 
                                                     timeout=self.options.timeout, verbose=self.options.debug)
            gid = self._get_gid(type='user')
            self.registry = None 
            self.logger.info("Writing certificate to %s"%cert_file)
            gid.save_to_file(cert_file)
        except:
            self.logger.info("Failed to download Registry issued cert")

        return cert_file

    def get_cached_gid(self, file):
        """
        Return a cached gid    
        """
        gid = None 
        if (os.path.isfile(file)):
            gid = GID(filename=file)
        return gid

    # xxx opts unused
    def get_gid(self, opts, args):
        """
        Get the specify gid and save it to file
        """
        hrn = None
        if args:
            hrn = args[0]
        gid = self._get_gid(hrn)
        self.logger.debug("Sfi.get_gid-> %s" % gid.save_to_string(save_parents=True))
        return gid

    def _get_gid(self, hrn=None, type=None):
        """
        git_gid helper. Retrive the gid from the registry and save it to file.
        """
        
        if not hrn:
            hrn = self.user
 
        gidfile = os.path.join(self.options.sfi_dir, hrn + ".gid")
        gid = self.get_cached_gid(gidfile)
        if not gid:
            user_cred = self.get_user_cred()
            records = self.registry.Resolve(hrn, user_cred.save_to_string(save_parents=True))
            if not records:
                raise RecordNotFound(args[0])
            record = records[0]
            if type:
                record=None
                for rec in records:
                   if type == rec['type']:
                        record = rec 
            if not record:
                raise RecordNotFound(args[0])
            
            gid = GID(string=record['gid'])
            self.logger.info("Writing gid to %s"%gidfile)
            gid.save_to_file(filename=gidfile)
        return gid   
                
     
    def get_cached_credential(self, file):
        """
        Return a cached credential only if it hasn't expired.
        """
        if (os.path.isfile(file)):
            credential = Credential(filename=file)
            # make sure it isnt expired 
            if not credential.get_expiration or \
               datetime.datetime.today() < credential.get_expiration():
                return credential
        return None 
 
    def get_user_cred(self):
        file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".cred")
        return self.get_cred(file, 'user', self.user)

    def get_auth_cred(self):
        if not self.authority:
            self.logger.critical("no authority specified. Use -a or set SF_AUTH")
            sys.exit(-1)
        file = os.path.join(self.options.sfi_dir, self.authority + ".cred")
        return self.get_cred(file, 'authority', self.authority)

    def get_slice_cred(self, name):
        file = os.path.join(self.options.sfi_dir, "slice_" + get_leaf(name) + ".cred")
        return self.get_cred(file, 'slice', name)
 
    def get_cred(self, file, type, hrn):
        # attempt to load a cached credential 
        cred = self.get_cached_credential(file)    
        if not cred:
            if type in ['user']:
                cert_string = self.cert.save_to_string(save_parents=True)
                user_name = self.user.replace(self.authority + ".", '')
                if user_name.count(".") > 0:
                    user_name = user_name.replace(".", '_')
                    self.user = self.authority + "." + user_name
                cred_str = self.registry.GetSelfCredential(cert_string, hrn, "user")
            else:
                # bootstrap slice credential from user credential
                user_cred = self.get_user_cred().save_to_string(save_parents=True)
                cred_str = self.registry.GetCredential(user_cred, hrn, type)
            
            if not cred_str:
                self.logger.critical("Failed to get %s credential" % type)
                sys.exit(-1)
                
            cred = Credential(string=cred_str)
            cred.save_to_file(file, save_parents=True)
            self.logger.info("Writing %s credential to %s" %(type, file))

        return cred
 
    
    def get_rspec_file(self, rspec):
       if (os.path.isabs(rspec)):
          file = rspec
       else:
          file = os.path.join(self.options.sfi_dir, rspec)
       if (os.path.isfile(file)):
          return file
       else:
          self.logger.critical("No such rspec file %s"%rspec)
          sys.exit(1)
    
    def get_record_file(self, record):
       if (os.path.isabs(record)):
          file = record
       else:
          file = os.path.join(self.options.sfi_dir, record)
       if (os.path.isfile(file)):
          return file
       else:
          self.logger.critical("No such registry record file %s"%record)
          sys.exit(1)
    
    # xxx opts undefined
    def get_component_proxy_from_hrn(self, hrn):
        # direct connection to the nodes component manager interface
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        records = self.registry.Resolve(hrn, user_cred)
        records = filter_records('node', records)
        if not records:
            self.logger.warning("No such component:%r"% opts.component)
        record = records[0]
  
        return self.server_proxy(record['hostname'], CM_PORT, self.key_file, self.cert_file)
 
    def server_proxy(self, host, port, keyfile, certfile):
        """
        Return an instance of an xmlrpc server connection    
        """
        # port is appended onto the domain, before the path. Should look like:
        # http://domain:port/path
        host_parts = host.split('/')
        host_parts[0] = host_parts[0] + ":" + str(port)
        url =  "http://%s" %  "/".join(host_parts)    
        return sfaprotocol.server_proxy(url, keyfile, certfile, timeout=self.options.timeout, 
                                        verbose=self.options.debug)

    # xxx opts could be retrieved in self.options
    def server_proxy_from_opts(self, opts):
        """
        Return instance of an xmlrpc connection to a slice manager, aggregate
        or component server depending on the specified opts
        """
        server = self.slicemgr
        # direct connection to an aggregate
        if hasattr(opts, 'aggregate') and opts.aggregate:
            server = self.server_proxy(opts.aggregate, opts.port, self.key_file, self.cert_file)
        # direct connection to the nodes component manager interface
        if hasattr(opts, 'component') and opts.component:
            server = self.get_component_proxy_from_hrn(opts.component)    
 
        return server
    #==========================================================================
    # Following functions implement the commands
    #
    # Registry-related commands
    #==========================================================================
  
    def create_gid(self, opts, args):
        if len(args) < 1:
            self.print_help()
            sys.exit(1)
        target_hrn = args[0]
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        gid = self.registry.CreateGid(user_cred, target_hrn, self.cert.save_to_string())
        if opts.file:
            filename = opts.file
        else:
            filename = os.sep.join([self.options.sfi_dir, '%s.gid' % target_hrn])
        self.logger.info("writing %s gid to %s" % (target_hrn, filename))
        GID(string=gid).save_to_file(filename)
         
     
    # list entires in named authority registry
    def list(self, opts, args):
        if len(args)!= 1:
            self.print_help()
            sys.exit(1)
        hrn = args[0]
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        try:
            list = self.registry.List(hrn, user_cred)
        except IndexError:
            raise Exception, "Not enough parameters for the 'list' command"

        # filter on person, slice, site, node, etc.
        # THis really should be in the self.filter_records funct def comment...
        list = filter_records(opts.type, list)
        for record in list:
            print "%s (%s)" % (record['hrn'], record['type'])
        if opts.file:
            save_records_to_file(opts.file, list, opts.fileformat)
        return
    
    # show named registry record
    def show(self, opts, args):
        if len(args)!= 1:
            self.print_help()
            sys.exit(1)
        hrn = args[0]
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        records = self.registry.Resolve(hrn, user_cred)
        records = filter_records(opts.type, records)
        if not records:
            self.logger.error("No record of type %s"% opts.type)
        for record in records:
            if record['type'] in ['user']:
                record = UserRecord(dict=record)
            elif record['type'] in ['slice']:
                record = SliceRecord(dict=record)
            elif record['type'] in ['node']:
                record = NodeRecord(dict=record)
            elif record['type'].startswith('authority'):
                record = AuthorityRecord(dict=record)
            else:
                record = SfaRecord(dict=record)
            if (opts.format == "text"): 
                record.dump()  
            else:
                print record.save_to_string() 
        if opts.file:
            save_records_to_file(opts.file, records, opts.fileformat)
        return
    
    def delegate(self, opts, args):

        delegee_hrn = args[0]
        if opts.delegate_user:
            user_cred = self.get_user_cred()
            cred = self.delegate_cred(user_cred, delegee_hrn)
        elif opts.delegate_slice:
            slice_cred = self.get_slice_cred(opts.delegate_slice)
            cred = self.delegate_cred(slice_cred, delegee_hrn)
        else:
            self.logger.warning("Must specify either --user or --slice <hrn>")
            return
        delegated_cred = Credential(string=cred)
        object_hrn = delegated_cred.get_gid_object().get_hrn()
        if opts.delegate_user:
            dest_fn = os.path.join(self.options.sfi_dir, get_leaf(delegee_hrn) + "_"
                                  + get_leaf(object_hrn) + ".cred")
        elif opts.delegate_slice:
            dest_fn = os.path.join(self.options.sfi_dir, get_leaf(delegee_hrn) + "_slice_"
                                  + get_leaf(object_hrn) + ".cred")

        delegated_cred.save_to_file(dest_fn, save_parents=True)

        self.logger.info("delegated credential for %s to %s and wrote to %s"%(object_hrn, delegee_hrn,dest_fn))
    
    def delegate_cred(self, object_cred, hrn):
        # the gid and hrn of the object we are delegating
        if isinstance(object_cred, str):
            object_cred = Credential(string=object_cred) 
        object_gid = object_cred.get_gid_object()
        object_hrn = object_gid.get_hrn()
    
        if not object_cred.get_privileges().get_all_delegate():
            self.logger.error("Object credential %s does not have delegate bit set"%object_hrn)
            return

        # the delegating user's gid
        caller_gid = self._get_gid(self.user)
        caller_gidfile = os.path.join(self.options.sfi_dir, self.user + ".gid")
  
        # the gid of the user who will be delegated to
        delegee_gid = self._get_gid(hrn)
        delegee_hrn = delegee_gid.get_hrn()
        delegee_gidfile = os.path.join(self.options.sfi_dir, delegee_hrn + ".gid")
        delegee_gid.save_to_file(filename=delegee_gidfile)
        dcred = object_cred.delegate(delegee_gidfile, self.get_key_file(), caller_gidfile)
        return dcred.save_to_string(save_parents=True)
     
    # removed named registry record
    #   - have to first retrieve the record to be removed
    def remove(self, opts, args):
        auth_cred = self.get_auth_cred().save_to_string(save_parents=True)
        if len(args)!=1:
            self.print_help()
            sys.exit(1)
        hrn = args[0]
        type = opts.type 
        if type in ['all']:
            type = '*'
        return self.registry.Remove(hrn, auth_cred, type)
    
    # add named registry record
    def add(self, opts, args):
        auth_cred = self.get_auth_cred().save_to_string(save_parents=True)
        if len(args)!=1:
            self.print_help()
            sys.exit(1)
        record_filepath = args[0]
        rec_file = self.get_record_file(record_filepath)
        record = load_record_from_file(rec_file).as_dict()
        return self.registry.Register(record, auth_cred)
    
    # update named registry entry
    def update(self, opts, args):
        user_cred = self.get_user_cred()
        if len(args)!=1:
            self.print_help()
            sys.exit(1)
        rec_file = self.get_record_file(args[0])
        record = load_record_from_file(rec_file)
        if record['type'] == "user":
            if record.get_name() == user_cred.get_gid_object().get_hrn():
                cred = user_cred.save_to_string(save_parents=True)
            else:
                cred = self.get_auth_cred().save_to_string(save_parents=True)
        elif record['type'] in ["slice"]:
            try:
                cred = self.get_slice_cred(record.get_name()).save_to_string(save_parents=True)
            except sfaprotocol.ServerException, e:
               # XXX smbaker -- once we have better error return codes, update this
               # to do something better than a string compare
               if "Permission error" in e.args[0]:
                   cred = self.get_auth_cred().save_to_string(save_parents=True)
               else:
                   raise
        elif record.get_type() in ["authority"]:
            cred = self.get_auth_cred().save_to_string(save_parents=True)
        elif record.get_type() == 'node':
            cred = self.get_auth_cred().save_to_string(save_parents=True)
        else:
            raise "unknown record type" + record.get_type()
        record = record.as_dict()
        return self.registry.Update(record, cred)
  
    def get_trusted_certs(self, opts, args):
        """
        return uhe trusted certs at this interface 
        """ 
        trusted_certs = self.registry.get_trusted_certs()
        for trusted_cert in trusted_certs:
            gid = GID(string=trusted_cert)
            gid.dump()
            cert = Certificate(string=trusted_cert)
            self.logger.debug('Sfi.get_trusted_certs -> %r'%cert.get_subject())
        return 

    # ==================================================================
    # Slice-related commands
    # ==================================================================

    def version(self, opts, args):
        if opts.version_local:
            version=version_core()
        else:
            if opts.version_registry:
                server=self.registry
            else:
                server = self.server_proxy_from_opts(opts)
            result = server.GetVersion()
            version = ReturnValue.get_value(result)
        for (k,v) in version.iteritems():
            print "%-20s: %s"%(k,v)
        if opts.file:
            save_variable_to_file(version, opts.file, opts.fileformat)

    # list instantiated slices
    def slices(self, opts, args):
        """
        list instantiated slices
        """
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        creds = [user_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(user_cred, get_authority(self.authority))
            creds.append(delegated_cred)  
        server = self.server_proxy_from_opts(opts)
        call_args = [creds]
        if self.server_supports_options_arg(server):
            options = {'call_id': unique_call_id()}
            call_args.append(options)
        result = server.ListSlices(*call_args)
        value = ReturnValue.get_value(result)
        display_list(value)
        return
    
    # show rspec for named slice
    def resources(self, opts, args):
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        server = self.server_proxy_from_opts(opts)
   
        options = {'call_id': unique_call_id()}
        #panos add info options
        if opts.info:
            options['info'] = opts.info
        
        if args:
            cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
            hrn = args[0]
            options['geni_slice_urn'] = hrn_to_urn(hrn, 'slice')
        else:
            cred = user_cred
     
        creds = [cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(cred, get_authority(self.authority))
            creds.append(delegated_cred)
        if opts.rspec_version:
            version_manager = VersionManager()
            server_version = self.get_cached_server_version(server)
            if 'sfa' in server_version:
                # just request the version the client wants 
                options['geni_rspec_version'] = version_manager.get_version(opts.rspec_version).to_dict()
            else:
                # this must be a protogeni aggregate. We should request a v2 ad rspec
                # regardless of what the client user requested 
                options['geni_rspec_version'] = version_manager.get_version('ProtoGENI 2').to_dict()     
        else:
            options['geni_rspec_version'] = {'type': 'geni', 'version': '3.0'}
 
        call_args = [creds, options]
        result = server.ListResources(*call_args)
        value = ReturnValue.get_value(result)
        if opts.file is None:
            display_rspec(value, opts.format)
        else:
            save_rspec_to_file(value, opts.file)
        return

    # created named slice with given rspec
    def create(self, opts, args):
        server = self.server_proxy_from_opts(opts)
        server_version = self.get_cached_server_version(server)
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice')
        user_cred = self.get_user_cred()
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        delegated_cred = None
        if server_version.get('interface') == 'slicemgr':
            # delegate our cred to the slice manager
            # do not delegate cred to slicemgr...not working at the moment
            pass
            #if server_version.get('hrn'):
            #    delegated_cred = self.delegate_cred(slice_cred, server_version['hrn'])
            #elif server_version.get('urn'):
            #    delegated_cred = self.delegate_cred(slice_cred, urn_to_hrn(server_version['urn']))
                 
        rspec_file = self.get_rspec_file(args[1])
        rspec = open(rspec_file).read()

        # need to pass along user keys to the aggregate.
        # users = [
        #  { urn: urn:publicid:IDN+emulab.net+user+alice
        #    keys: [<ssh key A>, <ssh key B>]
        #  }]
        users = []
        slice_records = self.registry.Resolve(slice_urn, [user_cred.save_to_string(save_parents=True)])
        if slice_records and 'researcher' in slice_records[0] and slice_records[0]['researcher']!=[]:
            slice_record = slice_records[0]
            user_hrns = slice_record['researcher']
            user_urns = [hrn_to_urn(hrn, 'user') for hrn in user_hrns]
            user_records = self.registry.Resolve(user_urns, [user_cred.save_to_string(save_parents=True)])

            if 'sfa' not in server_version:
                users = pg_users_arg(user_records)
                rspec = RSpec(rspec)
                rspec.filter({'component_manager_id': server_version['urn']})
                rspec = RSpecConverter.to_pg_rspec(rspec.toxml(), content_type='request')
                creds = [slice_cred]
            else:
                users = sfa_users_arg(user_records, slice_record)
                creds = [slice_cred]
                if delegated_cred:
                    creds.append(delegated_cred)
        call_args = [slice_urn, creds, rspec, users]
        if self.server_supports_options_arg(server):
            options = {'call_id': unique_call_id()}
            call_args.append(options)
        result = server.CreateSliver(*call_args)
        value = ReturnValue.get_value(result)
        if opts.file is None:
            print value
        else:
            save_rspec_to_file (value, opts.file)
        return value

    # get a ticket for the specified slice
    def get_ticket(self, opts, args):
        slice_hrn, rspec_path = args[0], args[1]
        slice_urn = hrn_to_urn(slice_hrn, 'slice')
        user_cred = self.get_user_cred()
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        rspec_file = self.get_rspec_file(rspec_path) 
        rspec = open(rspec_file).read()
        server = self.server_proxy_from_opts(opts)
        ticket_string = server.GetTicket(slice_urn, creds, rspec, [])
        file = os.path.join(self.options.sfi_dir, get_leaf(slice_hrn) + ".ticket")
        self.logger.info("writing ticket to %s"%file)
        ticket = SfaTicket(string=ticket_string)
        ticket.save_to_file(filename=file, save_parents=True)

    def redeem_ticket(self, opts, args):
        ticket_file = args[0]
        
        # get slice hrn from the ticket
        # use this to get the right slice credential 
        ticket = SfaTicket(filename=ticket_file)
        ticket.decode()
        slice_hrn = ticket.gidObject.get_hrn()
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        #slice_hrn = ticket.attributes['slivers'][0]['hrn']
        user_cred = self.get_user_cred()
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        
        # get a list of node hostnames from the RSpec 
        tree = etree.parse(StringIO(ticket.rspec))
        root = tree.getroot()
        hostnames = root.xpath("./network/site/node/hostname/text()")
        
        # create an xmlrpc connection to the component manager at each of these
        # components and gall redeem_ticket
        connections = {}
        for hostname in hostnames:
            try:
                self.logger.info("Calling redeem_ticket at %(hostname)s " % locals())
                server = self.server_proxy(hostname, CM_PORT, self.key_file, \
                                         self.cert_file, self.options.debug)
                server.RedeemTicket(ticket.save_to_string(save_parents=True), slice_cred)
                self.logger.info("Success")
            except socket.gaierror:
                self.logger.error("redeem_ticket failed: Component Manager not accepting requests")
            except Exception, e:
                self.logger.log_exc(e.message)
        return
 
    # delete named slice
    def delete(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        server = self.server_proxy_from_opts(opts)
        call_args = [slice_urn, creds]
        if self.server_supports_options_arg(server):
            options = {'call_id': unique_call_id()}
            call_args.append(options)
        return server.DeleteSliver(*call_args) 
  
    # start named slice
    def start(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        server = self.server_proxy_from_opts(opts)
        return server.Start(slice_urn, creds)
    
    # stop named slice
    def stop(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        server = self.server_proxy_from_opts(opts)
        return server.Stop(slice_urn, creds)
    
    # reset named slice
    def reset(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        server = self.server_proxy_from_opts(opts)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        return server.reset_slice(creds, slice_urn)

    def renew(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        server = self.server_proxy_from_opts(opts)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        time = args[1]
        
        call_args = [slice_urn, creds, time]
        if self.server_supports_options_arg(server):
            options = {'call_id': unique_call_id()}
            call_args.append(options)
        result =  server.RenewSliver(*call_args)
        value = ReturnValue.get_value(result)
        return value


    def status(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        server = self.server_proxy_from_opts(opts)
        call_args = [slice_urn, creds]
        if self.server_supports_options_arg(server):
            options = {'call_id': unique_call_id()}
            call_args.append(options)
        result = server.SliverStatus(*call_args)
        value = ReturnValue.get_value(result)
        print value
        if opts.file:
            save_variable_to_file(value, opts.file, opts.fileformat)


    def shutdown(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        server = self.server_proxy_from_opts(opts)
        return server.Shutdown(slice_urn, creds)         
    
    def print_help (self):
        self.sfi_parser.print_help()
        self.cmd_parser.print_help()

    #
    # Main: parse arguments and dispatch to command
    #
    def dispatch(self, command, cmd_opts, cmd_args):
        return getattr(self, command)(cmd_opts, cmd_args)

    def main(self):
        self.sfi_parser = self.create_parser()
        (options, args) = self.sfi_parser.parse_args()
        self.options = options

        self.logger.setLevelFromOptVerbose(self.options.verbose)
        if options.hashrequest:
            self.hashrequest = True
 
        if len(args) <= 0:
            self.logger.critical("No command given. Use -h for help.")
            return -1
    
        command = args[0]
        self.cmd_parser = self.create_cmd_parser(command)
        (cmd_opts, cmd_args) = self.cmd_parser.parse_args(args[1:])

        self.set_servers()
        self.logger.info("Command=%s" % command)
        if command in ("resources"):
            self.logger.debug("resources cmd_opts %s" % cmd_opts.format)
        elif command in ("list", "show", "remove"):
            self.logger.debug("cmd_opts.type %s" % cmd_opts.type)
        self.logger.debug('cmd_args %s' % cmd_args)

        try:
            self.dispatch(command, cmd_opts, cmd_args)
        except KeyError:
            self.logger.critical ("Unknown command %s"%command)
            raise
            sys.exit(1)
    
        return
    
if __name__ == "__main__":
    Sfi().main()
