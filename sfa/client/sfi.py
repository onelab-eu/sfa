# 
# sfi.py - basic SFA command-line client
# the actual binary in sfa/clientbin essentially runs main()
# this module is used in sfascan
# 

import sys
sys.path.append('.')

import os, os.path
import socket
import datetime
import codecs
import pickle
from lxml import etree
from StringIO import StringIO
from optparse import OptionParser
from pprint import PrettyPrinter

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

from sfa.client.sfaclientlib import SfaClientBootstrap
from sfa.client.sfaserverproxy import SfaServerProxy, ServerException
from sfa.client.client_helper import pg_users_arg, sfa_users_arg
from sfa.client.return_value import ReturnValue

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
        self.user = None
        self.authority = None
        self.logger = sfi_logger
        self.logger.enable_console()
        self.available_names = [ tuple[0] for tuple in Sfi.available ]
        self.available_dict = dict (Sfi.available)
   
    # tuples command-name expected-args in the order in which they should appear in the help
    available = [ 
        ("version", ""),  
        ("list", "authority"),
        ("show", "name"),
        ("add", "record"),
        ("update", "record"),
        ("remove", "name"),
        ("slices", ""),
        ("resources", "[slice_hrn]"),
        ("create", "slice_hrn rspec"),
        ("delete", "slice_hrn"),
        ("status", "slice_hrn"),
        ("start", "slice_hrn"),
        ("stop", "slice_hrn"),
        ("reset", "slice_hrn"),
        ("renew", "slice_hrn time"),
        ("shutdown", "slice_hrn"),
        ("get_ticket", "slice_hrn rspec"),
        ("redeem_ticket", "ticket"),
        ("delegate", "name"),
        ("create_gid", "[name]"),
        ("get_trusted_certs", "cred"),
        ]

    def print_command_help (self, options):
        verbose=getattr(options,'verbose')
        format3="%18s %-15s %s"
        line=80*'-'
        if not verbose:
            print format3%("command","cmd_args","description")
            print line
        else:
            print line
            self.create_parser().print_help()
        for command in self.available_names:
            args=self.available_dict[command]
            method=getattr(self,command,None)
            doc=""
            if method: doc=getattr(method,'__doc__',"")
            if not doc: doc="*** no doc found ***"
            doc=doc.strip(" \t\n")
            doc=doc.replace("\n","\n"+35*' ')
            if verbose:
                print line
            print format3%(command,args,doc)
            if verbose:
                self.create_command_parser(command).print_help()

    def create_command_parser(self, command):
        if command not in self.available_dict:
            msg="Invalid command\n"
            msg+="Commands: "
            msg += ','.join(self.available_names)            
            self.logger.critical(msg)
            sys.exit(2)

        parser = OptionParser(usage="sfi [sfi_options] %s [cmd_options] %s" \
                                     % (command, self.available_dict[command]))

        # user specifies remote aggregate/sm/component                          
        if command in ("resources", "slices", "create", "delete", "start", "stop", 
                       "restart", "shutdown",  "get_ticket", "renew", "status"):
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
            parser.add_option("-R","--registry-version",
                              action="store_true", dest="version_registry", default=False,
                              help="probe registry version instead of sliceapi")
            parser.add_option("-l","--local",
                              action="store_true", dest="version_local", default=False,
                              help="display version of the local client")

        return parser

        
    def create_parser(self):

        # Generate command line parser
        parser = OptionParser(usage="sfi [sfi_options] command [cmd_options] [cmd_args]",
                             description="Commands: %s"%(" ".join(self.available_names)))
        parser.add_option("-r", "--registry", dest="registry",
                         help="root registry", metavar="URL", default=None)
        parser.add_option("-s", "--sliceapi", dest="sm", default=None, metavar="URL",
                         help="slice API - in general a SM URL, but can be used to talk to an aggregate")
        parser.add_option("-d", "--dir", dest="sfi_dir",
                         help="config & working directory - default is %default",
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
        # would it make sense to use ~/.ssh/id_rsa as a default here ?
        parser.add_option("-k", "--private-key",
                         action="store", dest="user_private_key", default=None,
                         help="point to the private key file to use if not yet installed in sfi_dir")
        parser.add_option("-t", "--timeout", dest="timeout", default=None,
                         help="Amout of time to wait before timing out the request")
        parser.add_option("-?", "--commands", 
                         action="store_true", dest="command_help", default=False,
                         help="one page summary on commands & exit")
        parser.disable_interspersed_args()

        return parser
        

    def print_help (self):
        self.sfi_parser.print_help()
        self.command_parser.print_help()

    #
    # Main: parse arguments and dispatch to command
    #
    def dispatch(self, command, command_options, command_args):
        return getattr(self, command)(command_options, command_args)

    def main(self):
        self.sfi_parser = self.create_parser()
        (options, args) = self.sfi_parser.parse_args()
        if options.command_help: 
            self.print_command_help(options)
            sys.exit(1)
        self.options = options

        self.logger.setLevelFromOptVerbose(self.options.verbose)

        if len(args) <= 0:
            self.logger.critical("No command given. Use -h for help.")
            self.print_command_help(options)
            return -1
    
        command = args[0]
        self.command_parser = self.create_command_parser(command)
        (command_options, command_args) = self.command_parser.parse_args(args[1:])
        self.command_options = command_options

        self.read_config () 
        self.bootstrap ()
        self.logger.info("Command=%s" % command)

        try:
            self.dispatch(command, command_options, command_args)
        except KeyError:
            self.logger.critical ("Unknown command %s"%command)
            raise
            sys.exit(1)
    
        return
    
    ####################
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
    
    # init self-signed cert, user credentials and gid
    def bootstrap (self):
        bootstrap = SfaClientBootstrap (self.user, self.reg_url, self.options.sfi_dir)
        # if -k is provided, use this to initialize private key
        if self.options.user_private_key:
            bootstrap.init_private_key_if_missing (self.options.user_private_key)
        else:
            # trigger legacy compat code if needed 
            # the name has changed from just <leaf>.pkey to <hrn>.pkey
            if not os.path.isfile(bootstrap.private_key_filename()):
                self.logger.info ("private key not found, trying legacy name")
                try:
                    legacy_private_key = os.path.join (self.options.sfi_dir, "%s.pkey"%get_leaf(self.user))
                    self.logger.debug("legacy_private_key=%s"%legacy_private_key)
                    bootstrap.init_private_key_if_missing (legacy_private_key)
                    self.logger.info("Copied private key from legacy location %s"%legacy_private_key)
                except:
                    self.logger.log_exc("Can't find private key ")
                    sys.exit(1)
            
        # make it bootstrap
        bootstrap.bootstrap_my_gid()
        # extract what's needed
        self.private_key = bootstrap.private_key()
        self.my_credential_string = bootstrap.my_credential_string ()
        self.my_gid = bootstrap.my_gid ()
        self.bootstrap = bootstrap


    def my_authority_credential_string(self):
        if not self.authority:
            self.logger.critical("no authority specified. Use -a or set SF_AUTH")
            sys.exit(-1)
        return self.bootstrap.authority_credential_string (self.authority)

    def slice_credential_string(self, name):
        return self.bootstrap.slice_credential_string (name)

    # xxx should be supported by sfaclientbootstrap as well
    def delegate_cred(self, object_cred, hrn, type='authority'):
        # the gid and hrn of the object we are delegating
        if isinstance(object_cred, str):
            object_cred = Credential(string=object_cred) 
        object_gid = object_cred.get_gid_object()
        object_hrn = object_gid.get_hrn()
    
        if not object_cred.get_privileges().get_all_delegate():
            self.logger.error("Object credential %s does not have delegate bit set"%object_hrn)
            return

        # the delegating user's gid
        caller_gidfile = self.my_gid()
  
        # the gid of the user who will be delegated to
        delegee_gid = self.bootstrap.gid(hrn,type)
        delegee_hrn = delegee_gid.get_hrn()
        dcred = object_cred.delegate(delegee_gid, self.private_key, caller_gidfile)
        return dcred.save_to_string(save_parents=True)
     
    #
    # Management of the servers
    # 

    def registry (self):
        # cache the result
        if not hasattr (self, 'registry_proxy'):
            self.logger.info("Contacting Registry at: %s"%self.reg_url)
            self.registry_proxy = SfaServerProxy(self.reg_url, self.private_key, self.my_gid, 
                                                 timeout=self.options.timeout, verbose=self.options.debug)  
        return self.registry_proxy

    def sliceapi (self):
        # cache the result
        if not hasattr (self, 'sliceapi_proxy'):
            # if the command exposes the --component option, figure it's hostname and connect at CM_PORT
            if hasattr(self.command_options,'component') and self.command_options.component:
                # resolve the hrn at the registry
                node_hrn = self.command_options.component
                records = self.registry().Resolve(node_hrn, self.my_credential_string)
                records = filter_records('node', records)
                if not records:
                    self.logger.warning("No such component:%r"% opts.component)
                record = records[0]
                cm_url = "http://%s:%d/"%(record['hostname'],CM_PORT)
                self.sliceapi_proxy=SfaServerProxy(cm_url, self.private_key, self.my_gid)
            else:
                # otherwise use what was provided as --sliceapi, or SFI_SM in the config
                self.logger.info("Contacting Slice Manager at: %s"%self.sm_url)
                self.sliceapi_proxy = SfaServerProxy(self.sm_url, self.private_key, self.my_gid, 
                                                     timeout=self.options.timeout, verbose=self.options.debug)  
        return self.sliceapi_proxy

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
            # cache version for 20 minutes
            cache.add(cache_key, version, ttl= 60*20)
            self.logger.info("Updating cache file %s" % cache_file)
            cache.save_to_file(cache_file)

        return version   
        
    ### resurrect this temporarily so we can support V1 aggregates for a while
    def server_supports_options_arg(self, server):
        """
        Returns true if server support the optional call_id arg, false otherwise. 
        """
        server_version = self.get_cached_server_version(server)
        result = False
        # xxx need to rewrite this 
        if int(server_version.get('geni_api')) >= 2:
            result = True
        return result

    def server_supports_call_id_arg(self, server):
        server_version = self.get_cached_server_version(server)
        result = False      
        if 'sfa' in server_version and 'code_tag' in server_version:
            code_tag = server_version['code_tag']
            code_tag_parts = code_tag.split("-")
            version_parts = code_tag_parts[0].split(".")
            major, minor = version_parts[0], version_parts[1]
            rev = code_tag_parts[1]
            if int(major) == 1 and minor == 0 and build >= 22:
                result = True
        return result                 

    ### ois = options if supported
    # to be used in something like serverproxy.Method (arg1, arg2, *self.ois(api_options))
    def ois (self, server, option_dict):
        if self.server_supports_options_arg (server): 
            return [option_dict]
        elif self.server_supports_call_id_arg (server):
            return [ unique_call_id () ]
        else: 
            return []

    ### cis = call_id if supported - like ois
    def cis (self, server):
        if self.server_supports_call_id_arg (server):
            return [ unique_call_id ]
        else:
            return []

    ######################################## miscell utilities
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
    

    #==========================================================================
    # Following functions implement the commands
    #
    # Registry-related commands
    #==========================================================================
  
    def version(self, options, args):
        """
        display an SFA server version (GetVersion) 
or version information about sfi itself
        """
        if options.version_local:
            version=version_core()
        else:
            if options.version_registry:
                server=self.registry()
            else:
                server = self.sliceapi()
            result = server.GetVersion()
            version = ReturnValue.get_value(result)
        pprinter = PrettyPrinter(indent=4)
        pprinter.pprint(version)
        if options.file:
            save_variable_to_file(version, options.file, options.fileformat)

    def list(self, options, args):
        """
        list entries in named authority registry (List)
        """
        if len(args)!= 1:
            self.print_help()
            sys.exit(1)
        hrn = args[0]
        try:
            list = self.registry().List(hrn, self.my_credential_string)
        except IndexError:
            raise Exception, "Not enough parameters for the 'list' command"

        # filter on person, slice, site, node, etc.
        # THis really should be in the self.filter_records funct def comment...
        list = filter_records(options.type, list)
        for record in list:
            print "%s (%s)" % (record['hrn'], record['type'])
        if options.file:
            save_records_to_file(options.file, list, options.fileformat)
        return
    
    def show(self, options, args):
        """
        show details about named registry record (Resolve)
        """
        if len(args)!= 1:
            self.print_help()
            sys.exit(1)
        hrn = args[0]
        records = self.registry().Resolve(hrn, self.my_credential_string)
        records = filter_records(options.type, records)
        if not records:
            self.logger.error("No record of type %s"% options.type)
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
            if (options.format == "text"): 
                record.dump()  
            else:
                print record.save_to_string() 
        if options.file:
            save_records_to_file(options.file, records, options.fileformat)
        return
    
    def add(self, options, args):
        "add record into registry from xml file (Register)"
        auth_cred = self.my_authority_credential_string()
        if len(args)!=1:
            self.print_help()
            sys.exit(1)
        record_filepath = args[0]
        rec_file = self.get_record_file(record_filepath)
        record = load_record_from_file(rec_file).as_dict()
        return self.registry().Register(record, auth_cred)
    
    def update(self, options, args):
        "update record into registry from xml file (Update)"
        if len(args)!=1:
            self.print_help()
            sys.exit(1)
        rec_file = self.get_record_file(args[0])
        record = load_record_from_file(rec_file)
        if record['type'] == "user":
            if record.get_name() == self.user:
                cred = self.my_credential_string
            else:
                cred = self.my_authority_credential_string()
        elif record['type'] in ["slice"]:
            try:
                cred = self.slice_credential_string(record.get_name())
            except ServerException, e:
               # XXX smbaker -- once we have better error return codes, update this
               # to do something better than a string compare
               if "Permission error" in e.args[0]:
                   cred = self.my_authority_credential_string()
               else:
                   raise
        elif record.get_type() in ["authority"]:
            cred = self.my_authority_credential_string()
        elif record.get_type() == 'node':
            cred = self.my_authority_credential_string()
        else:
            raise "unknown record type" + record.get_type()
        record = record.as_dict()
        return self.registry().Update(record, cred)
  
    def remove(self, options, args):
        "remove registry record by name (Remove)"
        auth_cred = self.my_authority_credential_string()
        if len(args)!=1:
            self.print_help()
            sys.exit(1)
        hrn = args[0]
        type = options.type 
        if type in ['all']:
            type = '*'
        return self.registry().Remove(hrn, auth_cred, type)
    
    # ==================================================================
    # Slice-related commands
    # ==================================================================

    def slices(self, options, args):
        "list instantiated slices (ListSlices) - returns urn's"
        server = self.sliceapi()
        # creds
        creds = [self.my_credential_string]
        if options.delegate:
            delegated_cred = self.delegate_cred(self.my_credential_string, get_authority(self.authority))
            creds.append(delegated_cred)  
        # options and call_id when supported
        api_options = {}
	api_options['call_id']=unique_call_id()
        result = server.ListSlices(creds, *self.ois(server,api_options))
        value = ReturnValue.get_value(result)
        display_list(value)
        return
    
    # show rspec for named slice
    def resources(self, options, args):
        """
        with no arg, discover available resources, (ListResources)
or with an slice hrn, shows currently provisioned resources
        """
        server = self.sliceapi()

        # set creds
        creds = []
        if args:
            creds.append(self.slice_credential_string(args[0]))
        else:
            creds.append(self.my_credential_string)
        if options.delegate:
            creds.append(self.delegate_cred(cred, get_authority(self.authority)))
       
        # no need to check if server accepts the options argument since the options has
        # been a required argument since v1 API   
        api_options = {}
        # always send call_id to v2 servers
        api_options ['call_id'] = unique_call_id()
        # ask for cached value if available
        api_options ['cached'] = True
        if args:
            hrn = args[0]
            api_options['geni_slice_urn'] = hrn_to_urn(hrn, 'slice')
        if options.info:
            api_options['info'] = options.info
        if options.rspec_version:
            version_manager = VersionManager()
            server_version = self.get_cached_server_version(server)
            if 'sfa' in server_version:
                # just request the version the client wants
                api_options['geni_rspec_version'] = version_manager.get_version(options.rspec_version).to_dict()
            else:
                api_options['geni_rspec_version'] = {'type': 'geni', 'version': '3.0'}    
        else:
            api_options['geni_rspec_version'] = {'type': 'geni', 'version': '3.0'}    
        result = server.ListResources (creds, api_options)
        value = ReturnValue.get_value(result)
        if options.file is None:
            display_rspec(value, options.format)
        else:
            save_rspec_to_file(value, options.file)
        return

    def create(self, options, args):
        """
        create or update named slice with given rspec
        """
        server = self.sliceapi()

        # xxx do we need to check usage (len(args)) ?
        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice')

        # credentials
        creds = [self.slice_credential_string(slice_hrn)]
        delegated_cred = None
        server_version = self.get_cached_server_version(server)
        if server_version.get('interface') == 'slicemgr':
            # delegate our cred to the slice manager
            # do not delegate cred to slicemgr...not working at the moment
            pass
            #if server_version.get('hrn'):
            #    delegated_cred = self.delegate_cred(slice_cred, server_version['hrn'])
            #elif server_version.get('urn'):
            #    delegated_cred = self.delegate_cred(slice_cred, urn_to_hrn(server_version['urn']))
                
        # rspec 
        rspec_file = self.get_rspec_file(args[1])
        rspec = open(rspec_file).read()

        # users
        # need to pass along user keys to the aggregate.
        # users = [
        #  { urn: urn:publicid:IDN+emulab.net+user+alice
        #    keys: [<ssh key A>, <ssh key B>]
        #  }]
        users = []
        slice_records = self.registry().Resolve(slice_urn, [self.my_credential_string])
        if slice_records and 'researcher' in slice_records[0] and slice_records[0]['researcher']!=[]:
            slice_record = slice_records[0]
            user_hrns = slice_record['researcher']
            user_urns = [hrn_to_urn(hrn, 'user') for hrn in user_hrns]
            user_records = self.registry().Resolve(user_urns, [self.my_credential_string])

            if 'sfa' not in server_version:
                users = pg_users_arg(user_records)
                rspec = RSpec(rspec)
                rspec.filter({'component_manager_id': server_version['urn']})
                rspec = RSpecConverter.to_pg_rspec(rspec.toxml(), content_type='request')
            else:
                users = sfa_users_arg(user_records, slice_record)
        
        # do not append users, keys, or slice tags. Anything 
        # not contained in this request will be removed from the slice

        # CreateSliver has supported the options argument for a while now so it should
        # be safe to assume this server support it
        api_options = {}
        api_options ['append'] = False
        api_options ['call_id'] = unique_call_id()

        result = server.CreateSliver(slice_urn, creds, rspec, users, *self.ois(server, api_options))
        value = ReturnValue.get_value(result)
        if options.file is None:
            print value
        else:
            save_rspec_to_file (value, options.file)
        return value

    def delete(self, options, args):
        """
        delete named slice (DeleteSliver)
        """
        server = self.sliceapi()

        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 

        # creds
        slice_cred = self.slice_credential_string(slice_hrn)
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        
        # options and call_id when supported
        api_options = {}
        api_options ['call_id'] = unique_call_id()
        result = server.DeleteSliver(slice_urn, creds, *self.ois(server, api_options ) )
        # xxx no ReturnValue ??
        return result
  
    def status(self, options, args):
        """
        retrieve slice status (SliverStatus)
        """
        server = self.sliceapi()

        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 

        # creds 
        slice_cred = self.slice_credential_string(slice_hrn)
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)

        # options and call_id when supported
        api_options = {}
	api_options['call_id']=unique_call_id()
        result = server.SliverStatus(slice_urn, creds, *self.ois(server,api_options))
        value = ReturnValue.get_value(result)
        print value
        if options.file:
            save_variable_to_file(value, options.file, options.fileformat)

    def start(self, options, args):
        """
        start named slice (Start)
        """
        server = self.sliceapi()

        # the slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        
        # cred
        slice_cred = self.slice_credential_string(args[0])
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        # xxx Thierry - does this not need an api_options as well ?
        return server.Start(slice_urn, creds)
    
    def stop(self, options, args):
        """
        stop named slice (Stop)
        """
        server = self.sliceapi()
        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        # cred
        slice_cred = self.slice_credential_string(args[0])
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        return server.Stop(slice_urn, creds)
    
    # reset named slice
    def reset(self, options, args):
        """
        reset named slice (reset_slice)
        """
        server = self.sliceapi()
        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        # cred
        slice_cred = self.slice_credential_string(args[0])
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        return server.reset_slice(creds, slice_urn)

    def renew(self, options, args):
        """
        renew slice (RenewSliver)
        """
        server = self.sliceapi()
        # slice urn    
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        # creds
        slice_cred = self.slice_credential_string(args[0])
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        # time
        time = args[1]
        # options and call_id when supported
        api_options = {}
	api_options['call_id']=unique_call_id()
        result =  server.RenewSliver(slice_urn, creds, time, *self.ois(server,api_options))
        value = ReturnValue.get_value(result)
        return value


    def shutdown(self, options, args):
        """
        shutdown named slice (Shutdown)
        """
        server = self.sliceapi()
        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        # creds
        slice_cred = self.slice_credential_string(slice_hrn)
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        return server.Shutdown(slice_urn, creds)         
    

    def get_ticket(self, options, args):
        """
        get a ticket for the specified slice
        """
        server = self.sliceapi()
        # slice urn
        slice_hrn, rspec_path = args[0], args[1]
        slice_urn = hrn_to_urn(slice_hrn, 'slice')
        # creds
        slice_cred = self.slice_credential_string(slice_hrn)
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        # rspec
        rspec_file = self.get_rspec_file(rspec_path) 
        rspec = open(rspec_file).read()
        # options and call_id when supported
        api_options = {}
	api_options['call_id']=unique_call_id()
        # get ticket at the server
        ticket_string = server.GetTicket(slice_urn, creds, rspec, *self.ois(server,api_options))
        # save
        file = os.path.join(self.options.sfi_dir, get_leaf(slice_hrn) + ".ticket")
        self.logger.info("writing ticket to %s"%file)
        ticket = SfaTicket(string=ticket_string)
        ticket.save_to_file(filename=file, save_parents=True)

    def redeem_ticket(self, options, args):
        """
        Connects to nodes in a slice and redeems a ticket
(slice hrn is retrieved from the ticket)
        """
        ticket_file = args[0]
        
        # get slice hrn from the ticket
        # use this to get the right slice credential 
        ticket = SfaTicket(filename=ticket_file)
        ticket.decode()
        ticket_string = ticket.save_to_string(save_parents=True)

        slice_hrn = ticket.gidObject.get_hrn()
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        #slice_hrn = ticket.attributes['slivers'][0]['hrn']
        slice_cred = self.slice_credential_string(slice_hrn)
        
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
                cm_url="http://%s:%s/"%(hostname,CM_PORT)
                server = SfaServerProxy(cm_url, self.private_key, self.my_gid)
                server = self.server_proxy(hostname, CM_PORT, self.private_key, 
                                           timeout=self.options.timeout, verbose=self.options.debug)
                server.RedeemTicket(ticket_string, slice_cred)
                self.logger.info("Success")
            except socket.gaierror:
                self.logger.error("redeem_ticket failed on %s: Component Manager not accepting requests"%hostname)
            except Exception, e:
                self.logger.log_exc(e.message)
        return

    def create_gid(self, options, args):
        """
        Create a GID (CreateGid)
        """
        if len(args) < 1:
            self.print_help()
            sys.exit(1)
        target_hrn = args[0]
        gid = self.registry().CreateGid(self.my_credential_string, target_hrn, self.bootstrap.my_gid_string())
        if options.file:
            filename = options.file
        else:
            filename = os.sep.join([self.options.sfi_dir, '%s.gid' % target_hrn])
        self.logger.info("writing %s gid to %s" % (target_hrn, filename))
        GID(string=gid).save_to_file(filename)
         

    def delegate(self, options, args):
        """
        (locally) create delegate credential for use by given hrn
        """
        delegee_hrn = args[0]
        if options.delegate_user:
            cred = self.delegate_cred(self.my_credential_string, delegee_hrn, 'user')
        elif options.delegate_slice:
            slice_cred = self.slice_credential_string(options.delegate_slice)
            cred = self.delegate_cred(slice_cred, delegee_hrn, 'slice')
        else:
            self.logger.warning("Must specify either --user or --slice <hrn>")
            return
        delegated_cred = Credential(string=cred)
        object_hrn = delegated_cred.get_gid_object().get_hrn()
        if options.delegate_user:
            dest_fn = os.path.join(self.options.sfi_dir, get_leaf(delegee_hrn) + "_"
                                  + get_leaf(object_hrn) + ".cred")
        elif options.delegate_slice:
            dest_fn = os.path.join(self.options.sfi_dir, get_leaf(delegee_hrn) + "_slice_"
                                  + get_leaf(object_hrn) + ".cred")

        delegated_cred.save_to_file(dest_fn, save_parents=True)

        self.logger.info("delegated credential for %s to %s and wrote to %s"%(object_hrn, delegee_hrn,dest_fn))
    
    def get_trusted_certs(self, options, args):
        """
        return uhe trusted certs at this interface (get_trusted_certs)
        """ 
        trusted_certs = self.registry().get_trusted_certs()
        for trusted_cert in trusted_certs:
            gid = GID(string=trusted_cert)
            gid.dump()
            cert = Certificate(string=trusted_cert)
            self.logger.debug('Sfi.get_trusted_certs -> %r'%cert.get_subject())
        return 

