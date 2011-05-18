#! /usr/bin/env python

# sfi -- slice-based facility interface

import sys
sys.path.append('.')
import os, os.path
import tempfile
import traceback
import socket
import random
import datetime
from lxml import etree
from StringIO import StringIO
from types import StringTypes, ListType
from optparse import OptionParser
import zlib

from sfa.util.sfalogging import sfa_logger,sfa_logger_goes_to_console
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.gid import GID
from sfa.trust.credential import Credential
from sfa.util.sfaticket import SfaTicket
from sfa.util.record import SfaRecord, UserRecord, SliceRecord, NodeRecord, AuthorityRecord
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
from sfa.util.config import Config
from sfa.util.version import version_core

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
def save_rspec_to_file(rspec, filename):
    if not filename.endswith(".rspec"):
        filename = filename + ".rspec"

    f = open(filename, 'w')
    f.write(rspec)
    f.close()
    return

def save_records_to_file(filename, recordList):
    index = 0
    for record in recordList:
        if index > 0:
            save_record_to_file(filename + "." + str(index), record)
        else:
            save_record_to_file(filename, record)
        index = index + 1

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
    file(filename, "w").write(str)
    return


# load methods
def load_record_from_file(filename):
    str = file(filename, "r").read()
    record = SfaRecord(string=str)
    return record


import uuid
def unique_call_id(): return uuid.uuid4().urn

class Sfi:
    
    required_options=['verbose',  'debug',  'registry',  'sm',  'auth',  'user']

    # dummy to meet Sfi's expectations for its 'options' field
    # i.e. s/t we can do setattr on
    class DummyOptions:
        pass

    def __init__ (self,options=None):
        if options is None: options=Sfi.DummyOptions()
        for opt in Sfi.required_options:
            if not hasattr(options,opt): setattr(options,opt,None)
        if not hasattr(options,'sfi_dir'): options.sfi_dir=os.path.expanduser("~/.sfi/")
        self.options = options
        self.slicemgr = None
        self.registry = None
        self.user = None
        self.authority = None
        self.hashrequest = False
        sfa_logger_goes_to_console()
        self.logger=sfa_logger()
   
    def create_cmd_parser(self, command, additional_cmdargs=None):
        cmdargs = {"list": "authority",
                  "show": "name",
                  "remove": "name",
                  "add": "record",
                  "update": "record",
                  "aggregates": "[name]",
                  "registries": "[name]",
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

        if additional_cmdargs:
            cmdargs.update(additional_cmdargs)

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


        if command in ("resources", "show", "list"):
           parser.add_option("-o", "--output", dest="file",
                            help="output XML to file", metavar="FILE", default=None)
        
        if command in ("show", "list"):
           parser.add_option("-f", "--format", dest="format", type="choice",
                             help="display format ([text]|xml)", default="text",
                             choices=("text", "xml"))

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
        default_sfi_dir = os.path.expanduser("~/.sfi/")
        parser.add_option("-d", "--dir", dest="sfi_dir",
                         help="config & working directory - default is " + default_sfi_dir,
                         metavar="PATH", default=default_sfi_dir)
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
        parser.disable_interspersed_args()

        return parser
        
 
    def read_config(self):
       config_file = self.options.sfi_dir + os.sep + "sfi_config"
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
       self.key = Keypair(filename=key_file) 
       self.key_file = key_file
       self.cert_file = cert_file
       self.cert = GID(filename=cert_file) 
       # Establish connection to server(s)
       self.logger.info("Contacting Registry at: %s"%self.reg_url)
       self.registry = xmlrpcprotocol.get_server(self.reg_url, key_file, cert_file, self.options)  
       self.logger.info("Contacting Slice Manager at: %s"%self.sm_url)
       self.slicemgr = xmlrpcprotocol.get_server(self.sm_url, key_file, cert_file, self.options)

       return
    
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
        # try to get registry issued cert
        try:
            self.logger.info("Getting Registry issued cert")
            self.read_config()
            # *hack.  need to set registyr before _get_gid() is called 
            self.registry = xmlrpcprotocol.get_server(self.reg_url, key_file, cert_file, self.options)
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
        self.logger.debug("Sfi.get_gid-> %s",gid.save_to_string(save_parents=True))
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
            record = None
            if type:
                for rec in records:
                   if type == record['type']:
                        record = rec 
            if not record:
                raise RecordNotFound(args[0])
            gid = GID(string=records[0]['gid'])
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
    
    def load_publickey_string(self, fn):
       f = file(fn, "r")
       key_string = f.read()
    
       # if the filename is a private key file, then extract the public key
       if "PRIVATE KEY" in key_string:
           outfn = tempfile.mktemp()
           cmd = "openssl rsa -in " + fn + " -pubout -outform PEM -out " + outfn
           os.system(cmd)
           f = file(outfn, "r")
           key_string = f.read()
           os.remove(outfn)
    
       return key_string

    # xxx opts undefined
    def get_component_server_from_hrn(self, hrn):
        # direct connection to the nodes component manager interface
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        records = self.registry.Resolve(hrn, user_cred)
        records = filter_records('node', records)
        if not records:
            self.logger.warning("No such component:%r"% opts.component)
        record = records[0]
  
        return self.get_server(record['hostname'], CM_PORT, self.key_file, self.cert_file)
 
    def get_server(self, host, port, keyfile, certfile):
        """
        Return an instance of an xmlrpc server connection    
        """
        # port is appended onto the domain, before the path. Should look like:
        # http://domain:port/path
        host_parts = host.split('/')
        host_parts[0] = host_parts[0] + ":" + str(port)
        url =  "http://%s" %  "/".join(host_parts)    
        return xmlrpcprotocol.get_server(url, keyfile, certfile, self.options)

    # xxx opts could be retrieved in self.options
    def get_server_from_opts(self, opts):
        """
        Return instance of an xmlrpc connection to a slice manager, aggregate
        or component server depending on the specified opts
        """
        server = self.slicemgr
        # direct connection to an aggregate
        if hasattr(opts, 'aggregate') and opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, self.cert_file)
        # direct connection to the nodes component manager interface
        if hasattr(opts, 'component') and opts.component:
            server = self.get_component_server_from_hrn(opts.component)    
 
        return server
    #==========================================================================
    # Following functions implement the commands
    #
    # Registry-related commands
    #==========================================================================
  
    def dispatch(self, command, cmd_opts, cmd_args):
        return getattr(self, command)(cmd_opts, cmd_args)
 
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
            file = opts.file
            if not file.startswith(os.sep):
                file = os.path.join(self.options.sfi_dir, file)
            save_records_to_file(file, list)
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
            print "No record of type", opts.type
        for record in records:
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
            if (opts.format == "text"): 
                record.dump()  
            else:
                print record.save_to_string() 
       
        if opts.file:
            file = opts.file
            if not file.startswith(os.sep):
                file = os.path.join(self.options.sfi_dir, file)
            save_records_to_file(file, records)
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
            except xmlrpcprotocol.ServerException, e:
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
            cert = Certificate(string=trusted_cert)
            self.logger.debug('Sfi.get_trusted_certs -> %r'%cert.get_subject())
        return 

    def aggregates(self, opts, args):
        """
        return a list of details about known aggregates
        """
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = None
        if args:
            hrn = args[0]

        result = self.registry.get_aggregates(user_cred, hrn)
        display_list(result)
        return 

    def registries(self, opts, args):
        """
        return a list of details about known registries
        """
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = None
        if args:
            hrn = args[0]
        result = self.registry.get_registries(user_cred, hrn)
        display_list(result)
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
                server = self.get_server_from_opts(opts)
            version=server.GetVersion()
        for (k,v) in version.iteritems():
            print "%-20s: %s"%(k,v)

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
        server = self.get_server_from_opts(opts)
        #results = server.ListSlices(creds, unique_call_id())
        results = server.ListSlices(creds)
        display_list(results)
        return
    
    # show rspec for named slice
    def resources(self, opts, args):
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        server = self.slicemgr
        call_options = {}
        server = self.get_server_from_opts(opts)
        
        if args:
            cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
            hrn = args[0]
	    call_options = {'geni_slice_urn': hrn_to_urn(hrn, 'slice')}
        else:
            cred = user_cred
            hrn = None
     
        creds = [cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(cred, get_authority(self.authority))
            creds.append(delegated_cred)
        if opts.rspec_version:
            call_options['rspec_version'] = opts.rspec_version 
        #panos add info options
        if opts.info:
            call_options['info'] = opts.info 
        result = server.ListResources(creds, call_options,unique_call_id())
        format = opts.format
        if opts.file is None:
            display_rspec(result, format)
        else:
            file = opts.file
            if not file.startswith(os.sep):
                file = os.path.join(self.options.sfi_dir, file)
            save_rspec_to_file(result, file)
        return
    
    # created named slice with given rspec
    def create(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        user_cred = self.get_user_cred()
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        rspec_file = self.get_rspec_file(args[1])
        rspec = open(rspec_file).read()

        # users = [
        #  { urn: urn:publicid:IDN+emulab.net+user+alice
        #    keys: [<ssh key A>, <ssh key B>] 
        #  }]
        users = []
        server = self.get_server_from_opts(opts)
        version = server.GetVersion()
        if 'sfa' not in version:
            # need to pass along user keys if this request is going to a ProtoGENI aggregate 
            # ProtoGeni Aggregates will only install the keys of the user that is issuing the
            # request. So we will only pass in one user that contains the keys for all
            # users of the slice 
            user = {'urn': user_cred.get_gid_caller().get_urn(),
                    'keys': []}
            slice_record = self.registry.Resolve(slice_urn, creds)
            if slice_record and 'researchers' in slice_record:
                user_hrns = slice_record['researchers']
                user_urns = [hrn_to_urn(hrn, 'user') for hrn in user_hrns] 
                user_records = self.registry.Resolve(user_urns, creds)
                for user_record in user_records:
                    if 'keys' in user_record:
                        user['keys'].extend(user_record['keys'])
            users.append(user)             
        result =  server.CreateSliver(slice_urn, creds, rspec, users, unique_call_id())
        print result
        return result

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
        server = self.get_server_from_opts(opts)
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
                server = self.get_server(hostname, CM_PORT, self.key_file, \
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
        server = self.get_server_from_opts(opts)
        return server.DeleteSliver(slice_urn, creds, unique_call_id())
    
    # start named slice
    def start(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        server = self.get_server_from_opts(opts)
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
        server = self.get_server_from_opts(opts)
        return server.Stop(slice_urn, creds)
    
    # reset named slice
    def reset(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        server = self.get_server_from_opts(opts)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        return server.reset_slice(creds, slice_urn)

    def renew(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        server = self.get_server_from_opts(opts)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        time = args[1]
        return server.RenewSliver(slice_urn, creds, time, unique_call_id())


    def status(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        server = self.get_server_from_opts(opts)
        print server.SliverStatus(slice_urn, creds, unique_call_id())


    def shutdown(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        creds = [slice_cred]
        if opts.delegate:
            delegated_cred = self.delegate_cred(slice_cred, get_authority(self.authority))
            creds.append(delegated_cred)
        server = self.get_server_from_opts(opts)
        return server.Shutdown(slice_urn, creds)         
    
    def print_help (self):
        self.sfi_parser.print_help()
        self.cmd_parser.print_help()

    #
    # Main: parse arguments and dispatch to command
    #
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
        self.logger.debug('cmd_args %s',cmd_args)

        try:
            self.dispatch(command, cmd_opts, cmd_args)
        except KeyError:
            self.logger.critical ("Unknown command %s"%command)
            sys.exit(1)
    
        return
    
if __name__ == "__main__":
    Sfi().main()
