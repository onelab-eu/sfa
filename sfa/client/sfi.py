#
# sfi.py - basic SFA command-line client
# this module is also used in sfascan
#

import sys
sys.path.append('.')

import os, os.path
import socket
import re
import datetime
import codecs
import pickle
import json
import shutil
from lxml import etree
from StringIO import StringIO
from optparse import OptionParser
from pprint import PrettyPrinter
from tempfile import mkstemp

from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.gid import GID
from sfa.trust.credential import Credential
from sfa.trust.sfaticket import SfaTicket

from sfa.util.faults import SfaInvalidArgument
from sfa.util.sfalogging import sfi_logger
from sfa.util.xrn import get_leaf, get_authority, hrn_to_urn, Xrn
from sfa.util.config import Config
from sfa.util.version import version_core
from sfa.util.cache import Cache
from sfa.util.printable import printable

from sfa.storage.record import Record

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.rspec_converter import RSpecConverter
from sfa.rspecs.version_manager import VersionManager

from sfa.client.sfaclientlib import SfaClientBootstrap
from sfa.client.sfaserverproxy import SfaServerProxy, ServerException
from sfa.client.client_helper import pg_users_arg, sfa_users_arg
from sfa.client.return_value import ReturnValue
from sfa.client.candidates import Candidates
from sfa.client.manifolduploader import ManifoldUploader

CM_PORT=12346

from sfa.client.common import optparse_listvalue_callback, optparse_dictvalue_callback, \
    terminal_render, filter_records 

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
        record.dump(sort=True)
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


def credential_printable (cred):
    credential=Credential(cred=cred)
    result=""
    result += credential.get_summary_tostring()
    result += "\n"
    rights = credential.get_privileges()
    result += "type=%s\n" % credential.type    
    result += "version=%s\n" % credential.version    
    result += "rights=%s\n"%rights
    return result

def show_credentials (cred_s):
    if not isinstance (cred_s,list): cred_s = [cred_s]
    for cred in cred_s:
        print "Using Credential %s"%credential_printable(cred)

# save methods
def save_raw_to_file(var, filename, format="text", banner=None):
    if filename == "-":
        # if filename is "-", send it to stdout
        f = sys.stdout
    else:
        f = open(filename, "w")
    if banner:
        f.write(banner+"\n")
    if format == "text":
        f.write(str(var))
    elif format == "pickled":
        f.write(pickle.dumps(var))
    elif format == "json":
        if hasattr(json, "dumps"):
            f.write(json.dumps(var))   # python 2.6
        else:
            f.write(json.write(var))   # python 2.5
    else:
        # this should never happen
        print "unknown output format", format
    if banner:
        f.write('\n'+banner+"\n")

def save_rspec_to_file(rspec, filename):
    if not filename.endswith(".rspec"):
        filename = filename + ".rspec"
    f = open(filename, 'w')
    f.write("%s"%rspec)
    f.close()
    return

def save_records_to_file(filename, record_dicts, format="xml"):
    if format == "xml":
        index = 0
        for record_dict in record_dicts:
            if index > 0:
                save_record_to_file(filename + "." + str(index), record_dict)
            else:
                save_record_to_file(filename, record_dict)
            index = index + 1
    elif format == "xmllist":
        f = open(filename, "w")
        f.write("<recordlist>\n")
        for record_dict in record_dicts:
            record_obj=Record(dict=record_dict)
            f.write('<record hrn="' + record_obj.hrn + '" type="' + record_obj.type + '" />\n')
        f.write("</recordlist>\n")
        f.close()
    elif format == "hrnlist":
        f = open(filename, "w")
        for record_dict in record_dicts:
            record_obj=Record(dict=record_dict)
            f.write(record_obj.hrn + "\n")
        f.close()
    else:
        # this should never happen
        print "unknown output format", format

def save_record_to_file(filename, record_dict):
    record = Record(dict=record_dict)
    xml = record.save_as_xml()
    f=codecs.open(filename, encoding='utf-8',mode="w")
    f.write(xml)
    f.close()
    return

# minimally check a key argument
def check_ssh_key (key):
    good_ssh_key = r'^.*(?:ssh-dss|ssh-rsa)[ ]+[A-Za-z0-9+/=]+(?: .*)?$'
    return re.match(good_ssh_key, key, re.IGNORECASE)

# load methods
def load_record_from_opts(options):
    record_dict = {}
    if hasattr(options, 'xrn') and options.xrn:
        if hasattr(options, 'type') and options.type:
            xrn = Xrn(options.xrn, options.type)
        else:
            xrn = Xrn(options.xrn)
        record_dict['urn'] = xrn.get_urn()
        record_dict['hrn'] = xrn.get_hrn()
        record_dict['type'] = xrn.get_type()
    if hasattr(options, 'key') and options.key:
        try:
            pubkey = open(options.key, 'r').read()
        except IOError:
            pubkey = options.key
        if not check_ssh_key (pubkey):
            raise SfaInvalidArgument(name='key',msg="Could not find file, or wrong key format")
        record_dict['reg-keys'] = [pubkey]
    if hasattr(options, 'slices') and options.slices:
        record_dict['slices'] = options.slices
    if hasattr(options, 'reg_researchers') and options.reg_researchers is not None:
        record_dict['reg-researchers'] = options.reg_researchers
    if hasattr(options, 'email') and options.email:
        record_dict['email'] = options.email
    if hasattr(options, 'reg_pis') and options.reg_pis:
        record_dict['reg-pis'] = options.reg_pis

    # handle extra settings
    record_dict.update(options.extras)
    
    return Record(dict=record_dict)

def load_record_from_file(filename):
    f=codecs.open(filename, encoding="utf-8", mode="r")
    xml_string = f.read()
    f.close()
    return Record(xml=xml_string)


import uuid
def unique_call_id(): return uuid.uuid4().urn

########## a simple model for maintaing 3 doc attributes per command (instead of just one)
# essentially for the methods that implement a subcommand like sfi list
# we need to keep track of
# (*) doc         a few lines that tell what it does, still located in __doc__
# (*) args_string a simple one-liner that describes mandatory arguments
# (*) example     well, one or several releant examples
# 
# since __doc__ only accounts for one, we use this simple mechanism below
# however we keep doc in place for easier migration

from functools import wraps

# we use a list as well as a dict so we can keep track of the order
commands_list=[]
commands_dict={}

def declare_command (args_string, example,aliases=None):
    def wrap(m): 
        name=getattr(m,'__name__')
        doc=getattr(m,'__doc__',"-- missing doc --")
        doc=doc.strip(" \t\n")
        commands_list.append(name)
        # last item is 'canonical' name, so we can know which commands are aliases
        command_tuple=(doc, args_string, example,name)
        commands_dict[name]=command_tuple
        if aliases is not None:
            for alias in aliases:
                commands_list.append(alias)
                commands_dict[alias]=command_tuple
        @wraps(m)
        def new_method (*args, **kwds): return m(*args, **kwds)
        return new_method
    return wrap


def remove_none_fields (record):
    none_fields=[ k for (k,v) in record.items() if v is None ]
    for k in none_fields: del record[k]

##########

class Sfi:
    
    # dirty hack to make this class usable from the outside
    required_options=['verbose',  'debug',  'registry',  'sm',  'auth',  'user', 'user_private_key']

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
        ### various auxiliary material that we keep at hand 
        self.command=None
        # need to call this other than just 'config' as we have a command/method with that name
        self.config_instance=None
        self.config_file=None
        self.client_bootstrap=None

    ### suitable if no reasonable command has been provided
    def print_commands_help (self, options):
        verbose=getattr(options,'verbose')
        format3="%10s %-35s %s"
        format3offset=47
        line=80*'-'
        if not verbose:
            print format3%("command","cmd_args","description")
            print line
        else:
            print line
            self.create_parser_global().print_help()
        # preserve order from the code
        for command in commands_list:
            try:
                (doc, args_string, example, canonical) = commands_dict[command]
            except:
                print "Cannot find info on command %s - skipped"%command
                continue
            if verbose:
                print line
            if command==canonical:
                doc=doc.replace("\n","\n"+format3offset*' ')
                print format3%(command,args_string,doc)
                if verbose:
                    self.create_parser_command(command).print_help()
            else:
                print format3%(command,"<<alias for %s>>"%canonical,"")
            
    ### now if a known command was found we can be more verbose on that one
    def print_help (self):
        print "==================== Generic sfi usage"
        self.sfi_parser.print_help()
        (doc,_,example,canonical)=commands_dict[self.command]
        if canonical != self.command:
            print "\n==================== NOTE: %s is an alias for genuine %s"%(self.command,canonical)
            self.command=canonical
        print "\n==================== Purpose of %s"%self.command
        print doc
        print "\n==================== Specific usage for %s"%self.command
        self.command_parser.print_help()
        if example:
            print "\n==================== %s example(s)"%self.command
            print example

    def create_parser_global(self):
        # Generate command line parser
        parser = OptionParser(add_help_option=False,
                              usage="sfi [sfi_options] command [cmd_options] [cmd_args]",
                              description="Commands: %s"%(" ".join(commands_list)))
        parser.add_option("-r", "--registry", dest="registry",
                         help="root registry", metavar="URL", default=None)
        parser.add_option("-s", "--sliceapi", dest="sm", default=None, metavar="URL",
                         help="slice API - in general a SM URL, but can be used to talk to an aggregate")
        parser.add_option("-R", "--raw", dest="raw", default=None,
                          help="Save raw, unparsed server response to a file")
        parser.add_option("", "--rawformat", dest="rawformat", type="choice",
                          help="raw file format ([text]|pickled|json)", default="text",
                          choices=("text","pickled","json"))
        parser.add_option("", "--rawbanner", dest="rawbanner", default=None,
                          help="text string to write before and after raw output")
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
        parser.add_option("-h", "--help", 
                         action="store_true", dest="help", default=False,
                         help="one page summary on commands & exit")
        parser.disable_interspersed_args()

        return parser
        

    def create_parser_command(self, command):
        if command not in commands_dict:
            msg="Invalid command\n"
            msg+="Commands: "
            msg += ','.join(commands_list)            
            self.logger.critical(msg)
            sys.exit(2)

        # retrieve args_string
        (_, args_string, __,canonical) = commands_dict[command]

        parser = OptionParser(add_help_option=False,
                              usage="sfi [sfi_options] %s [cmd_options] %s"
                              % (command, args_string))
        parser.add_option ("-h","--help",dest='help',action='store_true',default=False,
                           help="Summary of one command usage")

        if canonical in ("config"):
            parser.add_option('-m', '--myslice', dest='myslice', action='store_true', default=False,
                              help='how myslice config variables as well')

        if canonical in ("version"):
            parser.add_option("-l","--local",
                              action="store_true", dest="version_local", default=False,
                              help="display version of the local client")

        if canonical in ("version", "trusted"):
            parser.add_option("-R","--registry_interface",
                              action="store_true", dest="registry_interface", default=False,
                              help="target the registry interface instead of slice interface")

        if canonical in ("register", "update"):
            parser.add_option('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn (mandatory)')
            parser.add_option('-t', '--type', dest='type', metavar='<type>', help='object type', default=None)
            parser.add_option('-e', '--email', dest='email', default="",  help="email (mandatory for users)") 
            parser.add_option('-k', '--key', dest='key', metavar='<key>', help='public key string or file', 
                              default=None)
            parser.add_option('-s', '--slices', dest='slices', metavar='<slices>', help='Set/replace slice xrns',
                              default='', type="str", action='callback', callback=optparse_listvalue_callback)
            parser.add_option('-r', '--researchers', dest='reg_researchers', metavar='<researchers>', 
                              help='Set/replace slice researchers - use -r none to reset', default=None, type="str", action='callback', 
                              callback=optparse_listvalue_callback)
            parser.add_option('-p', '--pis', dest='reg_pis', metavar='<PIs>', help='Set/replace Principal Investigators/Project Managers',
                              default='', type="str", action='callback', callback=optparse_listvalue_callback)
            parser.add_option ('-X','--extra',dest='extras',default={},type='str',metavar="<EXTRA_ASSIGNS>",
                               action="callback", callback=optparse_dictvalue_callback, nargs=1,
                               help="set extra/testbed-dependent flags, e.g. --extra enabled=true")

        # user specifies remote aggregate/sm/component                          
        if canonical in ("resources", "describe", "allocate", "provision", "delete", "allocate", "provision", 
                       "action", "shutdown", "renew", "status"):
            parser.add_option("-d", "--delegate", dest="delegate", default=None, 
                             action="store_true",
                             help="Include a credential delegated to the user's root"+\
                                  "authority in set of credentials for this call")

        # show_credential option
        if canonical in ("list","resources", "describe", "provision", "allocate", "register","update","remove","delete","status","renew"):
            parser.add_option("-C","--credential",dest='show_credential',action='store_true',default=False,
                              help="show credential(s) used in human-readable form")
        if canonical in ("renew"):
            parser.add_option("-l","--as-long-as-possible",dest='alap',action='store_true',default=False,
                              help="renew as long as possible")
        # registy filter option
        if canonical in ("list", "show", "remove"):
            parser.add_option("-t", "--type", dest="type", type="choice",
                            help="type filter ([all]|user|slice|authority|node|aggregate)",
                            choices=("all", "user", "slice", "authority", "node", "aggregate"),
                            default="all")
        if canonical in ("show"):
            parser.add_option("-k","--key",dest="keys",action="append",default=[],
                              help="specify specific keys to be displayed from record")
            parser.add_option("-n","--no-details",dest="no_details",action="store_true",default=False,
                              help="call Resolve without the 'details' option")
        if canonical in ("resources", "describe"):
            # rspec version
            parser.add_option("-r", "--rspec-version", dest="rspec_version", default="GENI 3",
                              help="schema type and version of resulting RSpec")
            # disable/enable cached rspecs
            parser.add_option("-c", "--current", dest="current", default=False,
                              action="store_true",  
                              help="Request the current rspec bypassing the cache. Cached rspecs are returned by default")
            # display formats
            parser.add_option("-f", "--format", dest="format", type="choice",
                             help="display format ([xml]|dns|ip)", default="xml",
                             choices=("xml", "dns", "ip"))
            #panos: a new option to define the type of information about resources a user is interested in
            parser.add_option("-i", "--info", dest="info",
                                help="optional component information", default=None)
            # a new option to retreive or not reservation-oriented RSpecs (leases)
            parser.add_option("-l", "--list_leases", dest="list_leases", type="choice",
                                help="Retreive or not reservation-oriented RSpecs ([resources]|leases|all )",
                                choices=("all", "resources", "leases"), default="resources")


        if canonical in ("resources", "describe", "allocate", "provision", "show", "list", "gid"):
           parser.add_option("-o", "--output", dest="file",
                            help="output XML to file", metavar="FILE", default=None)

        if canonical in ("show", "list"):
           parser.add_option("-f", "--format", dest="format", type="choice",
                             help="display format ([text]|xml)", default="text",
                             choices=("text", "xml"))

           parser.add_option("-F", "--fileformat", dest="fileformat", type="choice",
                             help="output file format ([xml]|xmllist|hrnlist)", default="xml",
                             choices=("xml", "xmllist", "hrnlist"))
        if canonical == 'list':
           parser.add_option("-r", "--recursive", dest="recursive", action='store_true',
                             help="list all child records", default=False)
           parser.add_option("-v", "--verbose", dest="verbose", action='store_true',
                             help="gives details, like user keys", default=False)
        if canonical in ("delegate"):
           parser.add_option("-u", "--user",
                             action="store_true", dest="delegate_user", default=False,
                             help="delegate your own credentials; default if no other option is provided")
           parser.add_option("-s", "--slice", dest="delegate_slices",action='append',default=[],
                             metavar="slice_hrn", help="delegate cred. for slice HRN")
           parser.add_option("-a", "--auths", dest='delegate_auths',action='append',default=[],
                             metavar='auth_hrn', help="delegate cred for auth HRN")
           # this primarily is a shorthand for -A my_hrn^
           parser.add_option("-p", "--pi", dest='delegate_pi', default=None, action='store_true',
                             help="delegate your PI credentials, so s.t. like -A your_hrn^")
           parser.add_option("-A","--to-authority",dest='delegate_to_authority',action='store_true',default=False,
                             help="""by default the mandatory argument is expected to be a user, 
use this if you mean an authority instead""")

        if canonical in ("myslice"):
            parser.add_option("-p","--password",dest='password',action='store',default=None,
                              help="specify mainfold password on the command line")
            parser.add_option("-s", "--slice", dest="delegate_slices",action='append',default=[],
                             metavar="slice_hrn", help="delegate cred. for slice HRN")
            parser.add_option("-a", "--auths", dest='delegate_auths',action='append',default=[],
                             metavar='auth_hrn', help="delegate PI cred for auth HRN")
            parser.add_option('-d', '--delegate', dest='delegate', help="Override 'delegate' from the config file")
            parser.add_option('-b', '--backend',  dest='backend',  help="Override 'backend' from the config file")
        
        return parser

        
    #
    # Main: parse arguments and dispatch to command
    #
    def dispatch(self, command, command_options, command_args):
        (doc, args_string, example, canonical) = commands_dict[command]
        method=getattr(self, canonical, None)
        if not method:
            print "sfi: unknown command %s"%command
            raise SystemExit,"Unknown command %s"%command
        return method(command_options, command_args)

    def main(self):
        self.sfi_parser = self.create_parser_global()
        (options, args) = self.sfi_parser.parse_args()
        if options.help: 
            self.print_commands_help(options)
            sys.exit(1)
        self.options = options

        self.logger.setLevelFromOptVerbose(self.options.verbose)

        if len(args) <= 0:
            self.logger.critical("No command given. Use -h for help.")
            self.print_commands_help(options)
            return -1
    
        # complete / find unique match with command set
        command_candidates = Candidates (commands_list)
        input = args[0]
        command = command_candidates.only_match(input)
        if not command:
            self.print_commands_help(options)
            sys.exit(1)
        # second pass options parsing
        self.command=command
        self.command_parser = self.create_parser_command(command)
        (command_options, command_args) = self.command_parser.parse_args(args[1:])
        if command_options.help:
            self.print_help()
            sys.exit(1)
        self.command_options = command_options

        self.read_config () 
        self.bootstrap ()
        self.logger.debug("Command=%s" % self.command)

        try:
            retcod = self.dispatch(command, command_options, command_args)
        except SystemExit:
            return 1
        except:
            self.logger.log_exc ("sfi command %s failed"%command)
            return 1
        return retcod
    
    ####################
    def read_config(self):
        config_file = os.path.join(self.options.sfi_dir,"sfi_config")
        shell_config_file  = os.path.join(self.options.sfi_dir,"sfi_config.sh")
        try:
            if Config.is_ini(config_file):
                config = Config (config_file)
            else:
                # try upgrading from shell config format
                fp, fn = mkstemp(suffix='sfi_config', text=True)  
                config = Config(fn)
                # we need to preload the sections we want parsed 
                # from the shell config
                config.add_section('sfi')
                # sface users should be able to use this same file to configure their stuff
                config.add_section('sface')
                # manifold users should be able to specify the details 
                # of their backend server here for 'sfi myslice'
                config.add_section('myslice')
                config.load(config_file)
                # back up old config
                shutil.move(config_file, shell_config_file)
                # write new config
                config.save(config_file)
                 
        except:
            self.logger.critical("Failed to read configuration file %s"%config_file)
            self.logger.info("Make sure to remove the export clauses and to add quotes")
            if self.options.verbose==0:
                self.logger.info("Re-run with -v for more details")
            else:
                self.logger.log_exc("Could not read config file %s"%config_file)
            sys.exit(1)
     
        self.config_instance=config
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
           self.logger.error("You need to set e.g. SFI_REGISTRY='http://your.registry.url:12345/' in %s" % config_file)
           errors += 1 

        # Set user HRN
        if (self.options.user is not None):
           self.user = self.options.user
        elif hasattr(config, "SFI_USER"):
           self.user = config.SFI_USER
        else:
           self.logger.error("You need to set e.g. SFI_USER='plc.princeton.username' in %s" % config_file)
           errors += 1 

        # Set authority HRN
        if (self.options.auth is not None):
           self.authority = self.options.auth
        elif hasattr(config, "SFI_AUTH"):
           self.authority = config.SFI_AUTH
        else:
           self.logger.error("You need to set e.g. SFI_AUTH='plc.princeton' in %s" % config_file)
           errors += 1 

        self.config_file=config_file
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
        client_bootstrap = SfaClientBootstrap (self.user, self.reg_url, self.options.sfi_dir,
                                               logger=self.logger)
        # if -k is provided, use this to initialize private key
        if self.options.user_private_key:
            client_bootstrap.init_private_key_if_missing (self.options.user_private_key)
        else:
            # trigger legacy compat code if needed 
            # the name has changed from just <leaf>.pkey to <hrn>.pkey
            if not os.path.isfile(client_bootstrap.private_key_filename()):
                self.logger.info ("private key not found, trying legacy name")
                try:
                    legacy_private_key = os.path.join (self.options.sfi_dir, "%s.pkey"%Xrn.unescape(get_leaf(self.user)))
                    self.logger.debug("legacy_private_key=%s"%legacy_private_key)
                    client_bootstrap.init_private_key_if_missing (legacy_private_key)
                    self.logger.info("Copied private key from legacy location %s"%legacy_private_key)
                except:
                    self.logger.log_exc("Can't find private key ")
                    sys.exit(1)
            
        # make it bootstrap
        client_bootstrap.bootstrap_my_gid()
        # extract what's needed
        self.private_key = client_bootstrap.private_key()
        self.my_credential_string = client_bootstrap.my_credential_string ()
        self.my_credential = {'geni_type': 'geni_sfa',
                              'geni_version': '3', 
                              'geni_value': self.my_credential_string}
        self.my_gid = client_bootstrap.my_gid ()
        self.client_bootstrap = client_bootstrap


    def my_authority_credential_string(self):
        if not self.authority:
            self.logger.critical("no authority specified. Use -a or set SF_AUTH")
            sys.exit(-1)
        return self.client_bootstrap.authority_credential_string (self.authority)

    def authority_credential_string(self, auth_hrn):
        return self.client_bootstrap.authority_credential_string (auth_hrn)

    def slice_credential_string(self, name):
        return self.client_bootstrap.slice_credential_string (name)

    def slice_credential(self, name):
        return {'geni_type': 'geni_sfa',
                'geni_version': '3',
                'geni_value': self.slice_credential_string(name)}    

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
        delegee_gid = self.client_bootstrap.gid(hrn,type)
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
                if not self.sm_url.startswith('http://') or self.sm_url.startswith('https://'):
                    self.sm_url = 'http://' + self.sm_url
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


    # helper function to analyze raw output
    # for main : return 0 if everything is fine, something else otherwise (mostly 1 for now)
    def success (self, raw):
        return_value=ReturnValue (raw)
        output=ReturnValue.get_output(return_value)
        # means everything is fine
        if not output: 
            return 0
        # something went wrong
        print 'ERROR:',output
        return 1

    #==========================================================================
    # Following functions implement the commands
    #
    # Registry-related commands
    #==========================================================================

    @declare_command("","")
    def config (self, options, args):
        "Display contents of current config"
        print "# From configuration file %s"%self.config_file
        flags=[ ('sfi', [ ('registry','reg_url'),
                          ('auth','authority'),
                          ('user','user'),
                          ('sm','sm_url'),
                          ]),
                ]
        if options.myslice:
            flags.append ( ('myslice', ['backend', 'delegate', 'platform', 'username'] ) )

        for (section, tuples) in flags:
            print "[%s]"%section
            try:
                for (external_name, internal_name) in tuples:
                    print "%-20s = %s"%(external_name,getattr(self,internal_name))
            except:
                for name in tuples:
                    varname="%s_%s"%(section.upper(),name.upper())
                    value=getattr(self.config_instance,varname)
                    print "%-20s = %s"%(name,value)
        # xxx should analyze result
        return 0

    @declare_command("","")
    def version(self, options, args):
        """
        display an SFA server version (GetVersion)
    or version information about sfi itself
        """
        if options.version_local:
            version=version_core()
        else:
            if options.registry_interface:
                server=self.registry()
            else:
                server = self.sliceapi()
            result = server.GetVersion()
            version = ReturnValue.get_value(result)
        if self.options.raw:
            save_raw_to_file(result, self.options.raw, self.options.rawformat, self.options.rawbanner)
        else:
            pprinter = PrettyPrinter(indent=4)
            pprinter.pprint(version)
        # xxx should analyze result
        return 0

    @declare_command("authority","")
    def list(self, options, args):
        """
        list entries in named authority registry (List)
        """
        if len(args)!= 1:
            self.print_help()
            sys.exit(1)
        hrn = args[0]
        opts = {}
        if options.recursive:
            opts['recursive'] = options.recursive
        
        if options.show_credential:
            show_credentials(self.my_credential_string)
        try:
            list = self.registry().List(hrn, self.my_credential_string, options)
        except IndexError:
            raise Exception, "Not enough parameters for the 'list' command"

        # filter on person, slice, site, node, etc.
        # This really should be in the self.filter_records funct def comment...
        list = filter_records(options.type, list)
        terminal_render (list, options)
        if options.file:
            save_records_to_file(options.file, list, options.fileformat)
        # xxx should analyze result
        return 0
    
    @declare_command("name","")
    def show(self, options, args):
        """
        show details about named registry record (Resolve)
        """
        if len(args)!= 1:
            self.print_help()
            sys.exit(1)
        hrn = args[0]
        # explicitly require Resolve to run in details mode
        resolve_options={}
        if not options.no_details: resolve_options['details']=True
        record_dicts = self.registry().Resolve(hrn, self.my_credential_string, resolve_options)
        record_dicts = filter_records(options.type, record_dicts)
        if not record_dicts:
            self.logger.error("No record of type %s"% options.type)
            return
        # user has required to focus on some keys
        if options.keys:
            def project (record):
                projected={}
                for key in options.keys:
                    try: projected[key]=record[key]
                    except: pass
                return projected
            record_dicts = [ project (record) for record in record_dicts ]
        records = [ Record(dict=record_dict) for record_dict in record_dicts ]
        for record in records:
            if (options.format == "text"):      record.dump(sort=True)  
            else:                               print record.save_as_xml() 
        if options.file:
            save_records_to_file(options.file, record_dicts, options.fileformat)
        # xxx should analyze result
        return 0
    
    # this historically was named 'add', it is now 'register' with an alias for legacy
    @declare_command("[xml-filename]","",['add'])
    def register(self, options, args):
        """create new record in registry (Register) 
    from command line options (recommended) 
    old-school method involving an xml file still supported"""

        auth_cred = self.my_authority_credential_string()
        if options.show_credential:
            show_credentials(auth_cred)
        record_dict = {}
        if len(args) > 1:
            self.print_help()
            sys.exit(1)
        if len(args)==1:
            try:
                record_filepath = args[0]
                rec_file = self.get_record_file(record_filepath)
                record_dict.update(load_record_from_file(rec_file).todict())
            except:
                print "Cannot load record file %s"%record_filepath
                sys.exit(1)
        if options:
            record_dict.update(load_record_from_opts(options).todict())
        # we should have a type by now
        if 'type' not in record_dict :
            self.print_help()
            sys.exit(1)
        # this is still planetlab dependent.. as plc will whine without that
        # also, it's only for adding
        if record_dict['type'] == 'user':
            if not 'first_name' in record_dict:
                record_dict['first_name'] = record_dict['hrn']
            if 'last_name' not in record_dict:
                record_dict['last_name'] = record_dict['hrn'] 
        register = self.registry().Register(record_dict, auth_cred)
        # xxx looks like the result here is not ReturnValue-compatible
        #return self.success (register)
        # xxx should analyze result
        return 0
    
    @declare_command("[xml-filename]","")
    def update(self, options, args):
        """update record into registry (Update) 
    from command line options (recommended) 
    old-school method involving an xml file still supported"""
        record_dict = {}
        if len(args) > 0:
            record_filepath = args[0]
            rec_file = self.get_record_file(record_filepath)
            record_dict.update(load_record_from_file(rec_file).todict())
        if options:
            record_dict.update(load_record_from_opts(options).todict())
        # at the very least we need 'type' here
        if 'type' not in record_dict:
            self.print_help()
            sys.exit(1)

        # don't translate into an object, as this would possibly distort
        # user-provided data; e.g. add an 'email' field to Users
        if record_dict['type'] in ['user']:
            if record_dict['hrn'] == self.user:
                cred = self.my_credential_string
            else:
                cred = self.my_authority_credential_string()
        elif record_dict['type'] in ['slice']:
            try:
                cred = self.slice_credential_string(record_dict['hrn'])
            except ServerException, e:
               # XXX smbaker -- once we have better error return codes, update this
               # to do something better than a string compare
               if "Permission error" in e.args[0]:
                   cred = self.my_authority_credential_string()
               else:
                   raise
        elif record_dict['type'] in ['authority']:
            cred = self.my_authority_credential_string()
        elif record_dict['type'] in ['node']:
            cred = self.my_authority_credential_string()
        else:
            raise "unknown record type" + record_dict['type']
        if options.show_credential:
            show_credentials(cred)
        update = self.registry().Update(record_dict, cred)
        # xxx looks like the result here is not ReturnValue-compatible
        #return self.success(update)
        # xxx should analyze result
        return 0
  
    @declare_command("hrn","")
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
        if options.show_credential:
            show_credentials(auth_cred)
        remove = self.registry().Remove(hrn, auth_cred, type)
        # xxx looks like the result here is not ReturnValue-compatible
        #return self.success (remove)
        # xxx should analyze result
        return 0
    
    # ==================================================================
    # Slice-related commands
    # ==================================================================

    # show rspec for named slice
    @declare_command("","")
    def resources(self, options, args):
        """
        discover available resources (ListResources)
        """
        server = self.sliceapi()

        # set creds
        creds = [self.my_credential]
        if options.delegate:
            creds.append(self.delegate_cred(cred, get_authority(self.authority)))
        if options.show_credential:
            show_credentials(creds)

        # no need to check if server accepts the options argument since the options has
        # been a required argument since v1 API
        api_options = {}
        # always send call_id to v2 servers
        api_options ['call_id'] = unique_call_id()
        # ask for cached value if available
        api_options ['cached'] = True
        if options.info:
            api_options['info'] = options.info
        if options.list_leases:
            api_options['list_leases'] = options.list_leases
        if options.current:
            if options.current == True:
                api_options['cached'] = False
            else:
                api_options['cached'] = True
        if options.rspec_version:
            version_manager = VersionManager()
            server_version = self.get_cached_server_version(server)
            if 'sfa' in server_version:
                # just request the version the client wants
                api_options['geni_rspec_version'] = version_manager.get_version(options.rspec_version).to_dict()
            else:
                api_options['geni_rspec_version'] = {'type': 'geni', 'version': '3'}
        else:
            api_options['geni_rspec_version'] = {'type': 'geni', 'version': '3'}
        list_resources = server.ListResources (creds, api_options)
        value = ReturnValue.get_value(list_resources)
        if self.options.raw:
            save_raw_to_file(list_resources, self.options.raw, self.options.rawformat, self.options.rawbanner)
        if options.file is not None:
            save_rspec_to_file(value, options.file)
        if (self.options.raw is None) and (options.file is None):
            display_rspec(value, options.format)
        return self.success(list_resources)

    @declare_command("slice_hrn","")
    def describe(self, options, args):
        """
        shows currently allocated/provisioned resources 
    of the named slice or set of slivers (Describe) 
        """
        server = self.sliceapi()

        # set creds
        creds = [self.slice_credential(args[0])]
        if options.delegate:
            creds.append(self.delegate_cred(cred, get_authority(self.authority)))
        if options.show_credential:
            show_credentials(creds)

        api_options = {'call_id': unique_call_id(),
                       'cached': True,
                       'info': options.info,
                       'list_leases': options.list_leases,
                       'geni_rspec_version': {'type': 'geni', 'version': '3'},
                      }
        if options.info:
            api_options['info'] = options.info

        if options.rspec_version:
            version_manager = VersionManager()
            server_version = self.get_cached_server_version(server)
            if 'sfa' in server_version:
                # just request the version the client wants
                api_options['geni_rspec_version'] = version_manager.get_version(options.rspec_version).to_dict()
            else:
                api_options['geni_rspec_version'] = {'type': 'geni', 'version': '3'}
        urn = Xrn(args[0], type='slice').get_urn()
        remove_none_fields(api_options) 
        describe = server.Describe([urn], creds, api_options)
        value = ReturnValue.get_value(describe)
        if self.options.raw:
            save_raw_to_file(describe, self.options.raw, self.options.rawformat, self.options.rawbanner)
        if options.file is not None:
            save_rspec_to_file(value['geni_rspec'], options.file)
        if (self.options.raw is None) and (options.file is None):
            display_rspec(value['geni_rspec'], options.format)
        return self.success (describe)

    @declare_command("slice_hrn [<sliver_urn>...]","")
    def delete(self, options, args):
        """
        de-allocate and de-provision all or named slivers of the named slice (Delete)
        """
        server = self.sliceapi()

        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 

        if len(args) > 1:
            # we have sliver urns
            sliver_urns = args[1:]
        else:
            # we provision all the slivers of the slice
            sliver_urns = [slice_urn]

        # creds
        slice_cred = self.slice_credential(slice_hrn)
        creds = [slice_cred]
        
        # options and call_id when supported
        api_options = {}
        api_options ['call_id'] = unique_call_id()
        if options.show_credential:
            show_credentials(creds)
        delete = server.Delete(sliver_urns, creds, *self.ois(server, api_options ) )
        value = ReturnValue.get_value(delete)
        if self.options.raw:
            save_raw_to_file(delete, self.options.raw, self.options.rawformat, self.options.rawbanner)
        else:
            print value
        return self.success (delete)

    @declare_command("slice_hrn rspec","")
    def allocate(self, options, args):
        """
         allocate resources to the named slice (Allocate)
        """
        server = self.sliceapi()
        server_version = self.get_cached_server_version(server)
        slice_hrn = args[0]
        slice_urn = Xrn(slice_hrn, type='slice').get_urn()

        # credentials
        creds = [self.slice_credential(slice_hrn)]

        delegated_cred = None
        if server_version.get('interface') == 'slicemgr':
            # delegate our cred to the slice manager
            # do not delegate cred to slicemgr...not working at the moment
            pass
            #if server_version.get('hrn'):
            #    delegated_cred = self.delegate_cred(slice_cred, server_version['hrn'])
            #elif server_version.get('urn'):
            #    delegated_cred = self.delegate_cred(slice_cred, urn_to_hrn(server_version['urn']))

        if options.show_credential:
            show_credentials(creds)

        # rspec
        rspec_file = self.get_rspec_file(args[1])
        rspec = open(rspec_file).read()
        api_options = {}
        api_options ['call_id'] = unique_call_id()
        # users
        sfa_users = []
        geni_users = []
        slice_records = self.registry().Resolve(slice_urn, [self.my_credential_string])
        remove_none_fields(slice_records[0])
        if slice_records and 'reg-researchers' in slice_records[0] and slice_records[0]['reg-researchers']!=[]:
            slice_record = slice_records[0]
            user_hrns = slice_record['reg-researchers']
            user_urns = [hrn_to_urn(hrn, 'user') for hrn in user_hrns]
            user_records = self.registry().Resolve(user_urns, [self.my_credential_string])
            sfa_users = sfa_users_arg(user_records, slice_record)
            geni_users = pg_users_arg(user_records)

        api_options['sfa_users'] = sfa_users
        api_options['geni_users'] = geni_users

        allocate = server.Allocate(slice_urn, creds, rspec, api_options)
        value = ReturnValue.get_value(allocate)
        if self.options.raw:
            save_raw_to_file(allocate, self.options.raw, self.options.rawformat, self.options.rawbanner)
        if options.file is not None:
            save_rspec_to_file (value['geni_rspec'], options.file)
        if (self.options.raw is None) and (options.file is None):
            print value
        return self.success(allocate)

    @declare_command("slice_hrn [<sliver_urn>...]","")
    def provision(self, options, args):
        """
        provision all or named already allocated slivers of the named slice (Provision)
        """
        server = self.sliceapi()
        server_version = self.get_cached_server_version(server)
        slice_hrn = args[0]
        slice_urn = Xrn(slice_hrn, type='slice').get_urn()
        if len(args) > 1:
            # we have sliver urns
            sliver_urns = args[1:]
        else:
            # we provision all the slivers of the slice
            sliver_urns = [slice_urn]

        # credentials
        creds = [self.slice_credential(slice_hrn)]
        delegated_cred = None
        if server_version.get('interface') == 'slicemgr':
            # delegate our cred to the slice manager
            # do not delegate cred to slicemgr...not working at the moment
            pass
            #if server_version.get('hrn'):
            #    delegated_cred = self.delegate_cred(slice_cred, server_version['hrn'])
            #elif server_version.get('urn'):
            #    delegated_cred = self.delegate_cred(slice_cred, urn_to_hrn(server_version['urn']))

        if options.show_credential:
            show_credentials(creds)

        api_options = {}
        api_options ['call_id'] = unique_call_id()

        # set the requtested rspec version
        version_manager = VersionManager()
        rspec_version = version_manager._get_version('geni', '3').to_dict()
        api_options['geni_rspec_version'] = rspec_version

        # users
        # need to pass along user keys to the aggregate.
        # users = [
        #  { urn: urn:publicid:IDN+emulab.net+user+alice
        #    keys: [<ssh key A>, <ssh key B>]
        #  }]
        users = []
        slice_records = self.registry().Resolve(slice_urn, [self.my_credential_string])
        if slice_records and 'reg-researchers' in slice_records[0] and slice_records[0]['reg-researchers']!=[]:
            slice_record = slice_records[0]
            user_hrns = slice_record['reg-researchers']
            user_urns = [hrn_to_urn(hrn, 'user') for hrn in user_hrns]
            user_records = self.registry().Resolve(user_urns, [self.my_credential_string])
            users = pg_users_arg(user_records)
        
        api_options['geni_users'] = users
        provision = server.Provision(sliver_urns, creds, api_options)
        value = ReturnValue.get_value(provision)
        if self.options.raw:
            save_raw_to_file(provision, self.options.raw, self.options.rawformat, self.options.rawbanner)
        if options.file is not None:
            save_rspec_to_file (value['geni_rspec'], options.file)
        if (self.options.raw is None) and (options.file is None):
            print value
        return self.success(provision)

    @declare_command("slice_hrn","")
    def status(self, options, args):
        """
        retrieve the status of the slivers belonging to the named slice (Status)
        """
        server = self.sliceapi()

        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 

        # creds 
        slice_cred = self.slice_credential(slice_hrn)
        creds = [slice_cred]

        # options and call_id when supported
        api_options = {}
        api_options['call_id']=unique_call_id()
        if options.show_credential:
            show_credentials(creds)
        status = server.Status([slice_urn], creds, *self.ois(server,api_options))
        value = ReturnValue.get_value(status)
        if self.options.raw:
            save_raw_to_file(status, self.options.raw, self.options.rawformat, self.options.rawbanner)
        else:
            print value
        return self.success (status)

    @declare_command("slice_hrn [<sliver_urn>...] action","")
    def action(self, options, args):
        """
        Perform the named operational action on all or named slivers of the named slice
        """
        server = self.sliceapi()
        api_options = {}
        # slice urn
        slice_hrn = args[0]
        slice_urn = Xrn(slice_hrn, type='slice').get_urn()
        if len(args) > 2:
            # we have sliver urns
            sliver_urns = args[1:-1]
        else:
            # we provision all the slivers of the slice
            sliver_urns = [slice_urn]
        action = args[-1]
        # cred
        slice_cred = self.slice_credential(args[0])
        creds = [slice_cred]
        if options.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        
        perform_action = server.PerformOperationalAction(sliver_urns, creds, action , api_options)
        value = ReturnValue.get_value(perform_action)
        if self.options.raw:
            save_raw_to_file(perform_action, self.options.raw, self.options.rawformat, self.options.rawbanner)
        else:
            print value
        return self.success (perform_action)

    @declare_command("slice_hrn [<sliver_urn>...] time",
                     "\n".join(["sfi renew onelab.ple.heartbeat 2015-04-31",
                                "sfi renew onelab.ple.heartbeat 2015-04-31T14:00:00Z",
                                "sfi renew onelab.ple.heartbeat +5d",
                                "sfi renew onelab.ple.heartbeat +3w",
                                "sfi renew onelab.ple.heartbeat +2m",]))
    def renew(self, options, args):
        """
        renew slice (Renew)
        """
        server = self.sliceapi()
        if len(args) < 2:
            self.print_help()
            sys.exit(1)
        slice_hrn = args[0]
        slice_urn = Xrn(slice_hrn, type='slice').get_urn()

        if len(args) > 2:
            # we have sliver urns
            sliver_urns = args[1:-1]
        else:
            # we provision all the slivers of the slice
            sliver_urns = [slice_urn]
        input_time = args[-1]

        # time: don't try to be smart on the time format, server-side will
        # creds
        slice_cred = self.slice_credential(args[0])
        creds = [slice_cred]
        # options and call_id when supported
        api_options = {}
        api_options['call_id']=unique_call_id()
        if options.alap:
            api_options['geni_extend_alap']=True
        if options.show_credential:
            show_credentials(creds)
        renew =  server.Renew(sliver_urns, creds, input_time, *self.ois(server,api_options))
        value = ReturnValue.get_value(renew)
        if self.options.raw:
            save_raw_to_file(renew, self.options.raw, self.options.rawformat, self.options.rawbanner)
        else:
            print value
        return self.success(renew)

    @declare_command("slice_hrn","")
    def shutdown(self, options, args):
        """
        shutdown named slice (Shutdown)
        """
        server = self.sliceapi()
        # slice urn
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        # creds
        slice_cred = self.slice_credential(slice_hrn)
        creds = [slice_cred]
        shutdown = server.Shutdown(slice_urn, creds)
        value = ReturnValue.get_value(shutdown)
        if self.options.raw:
            save_raw_to_file(shutdown, self.options.raw, self.options.rawformat, self.options.rawbanner)
        else:
            print value
        return self.success (shutdown)

    @declare_command("[name]","")
    def gid(self, options, args):
        """
        Create a GID (CreateGid)
        """
        if len(args) < 1:
            self.print_help()
            sys.exit(1)
        target_hrn = args[0]
        my_gid_string = open(self.client_bootstrap.my_gid()).read() 
        gid = self.registry().CreateGid(self.my_credential_string, target_hrn, my_gid_string)
        if options.file:
            filename = options.file
        else:
            filename = os.sep.join([self.options.sfi_dir, '%s.gid' % target_hrn])
        self.logger.info("writing %s gid to %s" % (target_hrn, filename))
        GID(string=gid).save_to_file(filename)
        # xxx should analyze result
        return 0
         
    ####################
    @declare_command("to_hrn","""$ sfi delegate -u -p -s ple.inria.heartbeat -s ple.inria.omftest ple.upmc.slicebrowser

  will locally create a set of delegated credentials for the benefit of ple.upmc.slicebrowser
  the set of credentials in the scope for this call would be
  (*) ple.inria.thierry_parmentelat.user_for_ple.upmc.slicebrowser.user.cred
      as per -u/--user
  (*) ple.inria.pi_for_ple.upmc.slicebrowser.user.cred
      as per -p/--pi
  (*) ple.inria.heartbeat.slice_for_ple.upmc.slicebrowser.user.cred
  (*) ple.inria.omftest.slice_for_ple.upmc.slicebrowser.user.cred
      because of the two -s options

""")
    def delegate (self, options, args):
        """
        (locally) create delegate credential for use by given hrn
    make sure to check for 'sfi myslice' instead if you plan
    on using MySlice
        """
        if len(args) != 1:
            self.print_help()
            sys.exit(1)
        to_hrn = args[0]
        # support for several delegations in the same call
        # so first we gather the things to do
        tuples=[]
        for slice_hrn in options.delegate_slices:
            message="%s.slice"%slice_hrn
            original = self.slice_credential_string(slice_hrn)
            tuples.append ( (message, original,) )
        if options.delegate_pi:
            my_authority=self.authority
            message="%s.pi"%my_authority
            original = self.my_authority_credential_string()
            tuples.append ( (message, original,) )
        for auth_hrn in options.delegate_auths:
            message="%s.auth"%auth_hrn
            original=self.authority_credential_string(auth_hrn)
            tuples.append ( (message, original, ) )
        # if nothing was specified at all at this point, let's assume -u
        if not tuples: options.delegate_user=True
        # this user cred
        if options.delegate_user:
            message="%s.user"%self.user
            original = self.my_credential_string
            tuples.append ( (message, original, ) )

        # default type for beneficial is user unless -A
        if options.delegate_to_authority:       to_type='authority'
        else:                                   to_type='user'

        # let's now handle all this
        # it's all in the filenaming scheme
        for (message,original) in tuples:
            delegated_string = self.client_bootstrap.delegate_credential_string(original, to_hrn, to_type)
            delegated_credential = Credential (string=delegated_string)
            filename = os.path.join ( self.options.sfi_dir,
                                      "%s_for_%s.%s.cred"%(message,to_hrn,to_type))
            delegated_credential.save_to_file(filename, save_parents=True)
            self.logger.info("delegated credential for %s to %s and wrote to %s"%(message,to_hrn,filename))
    
    ####################
    @declare_command("","""$ less +/myslice sfi_config
[myslice]
backend  = http://manifold.pl.sophia.inria.fr:7080
# the HRN that myslice uses, so that we are delegating to
delegate = ple.upmc.slicebrowser
# platform - this is a myslice concept
platform = ple
# username - as of this writing (May 2013) a simple login name
username = thierry

$ sfi myslice
  will first collect the slices that you are part of, then make sure
  all your credentials are up-to-date (read: refresh expired ones)
  then compute delegated credentials for user 'ple.upmc.slicebrowser'
  and upload them all on myslice backend, using 'platform' and 'user'.
  A password will be prompted for the upload part.

$ sfi -v myslice  -- or sfi -vv myslice
  same but with more and more verbosity

$ sfi m -b http://mymanifold.foo.com:7080/
  is synonym to sfi myslice as no other command starts with an 'm'
  and uses a custom backend for this one call
"""
) # declare_command
    def myslice (self, options, args):

        """ This helper is for refreshing your credentials at myslice; it will
    * compute all the slices that you currently have credentials on
    * refresh all your credentials (you as a user and pi, your slices)
    * upload them to the manifold backend server
    for last phase, sfi_config is read to look for the [myslice] section, 
    and namely the 'backend', 'delegate' and 'user' settings"""

        ##########
        if len(args)>0:
            self.print_help()
            sys.exit(1)
        # enable info by default
        self.logger.setLevelFromOptVerbose(self.options.verbose+1)
        ### the rough sketch goes like this
        # (0) produce a p12 file
        self.client_bootstrap.my_pkcs12()

        # (a) rain check for sufficient config in sfi_config
        myslice_dict={}
        myslice_keys=[ 'backend', 'delegate', 'platform', 'username']
        for key in myslice_keys:
            value=None
            # oct 2013 - I'm finding myself juggling with config files
            # so a couple of command-line options can now override config
            if hasattr(options,key) and getattr(options,key) is not None:
                value=getattr(options,key)
            else:
                full_key="MYSLICE_" + key.upper()
                value=getattr(self.config_instance,full_key,None)
            if value:   myslice_dict[key]=value
            else:       print "Unsufficient config, missing key %s in [myslice] section of sfi_config"%key
        if len(myslice_dict) != len(myslice_keys):
            sys.exit(1)

        # (b) figure whether we are PI for the authority where we belong
        self.logger.info("Resolving our own id %s"%self.user)
        my_records=self.registry().Resolve(self.user,self.my_credential_string)
        if len(my_records)!=1: print "Cannot Resolve %s -- exiting"%self.user; sys.exit(1)
        my_record=my_records[0]
        my_auths_all = my_record['reg-pi-authorities']
        self.logger.info("Found %d authorities that we are PI for"%len(my_auths_all))
        self.logger.debug("They are %s"%(my_auths_all))
        
        my_auths = my_auths_all
        if options.delegate_auths:
            my_auths = list(set(my_auths_all).intersection(set(options.delegate_auths)))
            self.logger.debug("Restricted to user-provided auths"%(my_auths))

        # (c) get the set of slices that we are in
        my_slices_all=my_record['reg-slices']
        self.logger.info("Found %d slices that we are member of"%len(my_slices_all))
        self.logger.debug("They are: %s"%(my_slices_all))
 
        my_slices = my_slices_all
        # if user provided slices, deal only with these - if they are found
        if options.delegate_slices:
            my_slices = list(set(my_slices_all).intersection(set(options.delegate_slices)))
            self.logger.debug("Restricted to user-provided slices: %s"%(my_slices))

        # (d) make sure we have *valid* credentials for all these
        hrn_credentials=[]
        hrn_credentials.append ( (self.user, 'user', self.my_credential_string,) )
        for auth_hrn in my_auths:
            hrn_credentials.append ( (auth_hrn, 'auth', self.authority_credential_string(auth_hrn),) )
        for slice_hrn in my_slices:
            hrn_credentials.append ( (slice_hrn, 'slice', self.slice_credential_string (slice_hrn),) )

        # (e) check for the delegated version of these
        # xxx todo add an option -a/-A? like for 'sfi delegate' for when we ever 
        # switch to myslice using an authority instead of a user
        delegatee_type='user'
        delegatee_hrn=myslice_dict['delegate']
        hrn_delegated_credentials = []
        for (hrn, htype, credential) in hrn_credentials:
            delegated_credential = self.client_bootstrap.delegate_credential_string (credential, delegatee_hrn, delegatee_type)
            # save these so user can monitor what she's uploaded
            filename = os.path.join ( self.options.sfi_dir,
                                      "%s.%s_for_%s.%s.cred"%(hrn,htype,delegatee_hrn,delegatee_type))
            with file(filename,'w') as f:
                f.write(delegated_credential)
            self.logger.debug("(Over)wrote %s"%filename)
            hrn_delegated_credentials.append ((hrn, htype, delegated_credential, filename, ))

        # (f) and finally upload them to manifold server
        # xxx todo add an option so the password can be set on the command line
        # (but *NOT* in the config file) so other apps can leverage this
        self.logger.info("Uploading on backend at %s"%myslice_dict['backend'])
        uploader = ManifoldUploader (logger=self.logger,
                                     url=myslice_dict['backend'],
                                     platform=myslice_dict['platform'],
                                     username=myslice_dict['username'],
                                     password=options.password)
        uploader.prompt_all()
        (count_all,count_success)=(0,0)
        for (hrn,htype,delegated_credential,filename) in hrn_delegated_credentials:
            # inspect
            inspect=Credential(string=delegated_credential)
            expire_datetime=inspect.get_expiration()
            message="%s (%s) [exp:%s]"%(hrn,htype,expire_datetime)
            if uploader.upload(delegated_credential,message=message):
                count_success+=1
            count_all+=1
        self.logger.info("Successfully uploaded %d/%d credentials"%(count_success,count_all))

        # at first I thought we would want to save these,
        # like 'sfi delegate does' but on second thought
        # it is probably not helpful as people would not
        # need to run 'sfi delegate' at all anymore
        if count_success != count_all: sys.exit(1)
        # xxx should analyze result
        return 0

    @declare_command("cred","")
    def trusted(self, options, args):
        """
        return the trusted certs at this interface (get_trusted_certs)
        """ 
        if options.registry_interface:
            server=self.registry()
        else:
            server = self.sliceapi()
        cred = self.my_authority_credential_string()
        trusted_certs = server.get_trusted_certs(cred)
        if not options.registry_interface:
            trusted_certs = ReturnValue.get_value(trusted_certs)

        for trusted_cert in trusted_certs:
            print "\n===========================================================\n"
            gid = GID(string=trusted_cert)
            gid.dump()
            cert = Certificate(string=trusted_cert)
            self.logger.debug('Sfi.trusted -> %r'%cert.get_subject())
            print "Certificate:\n%s\n\n"%trusted_cert
        # xxx should analyze result
        return 0
