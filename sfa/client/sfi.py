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
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.credential import Credential
from sfa.util.sfaticket import SfaTicket
from sfa.util.record import *
from sfa.util.namespace import *
from sfa.util.xmlrpcprotocol import ServerException
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
from sfa.util.config import Config
import zlib

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



class Sfi:

    slicemgr = None
    registry = None
    user = None
    authority = None
    options = None
    hashrequest = False
   
    def create_cmd_parser(self, command, additional_cmdargs=None):
        cmdargs = {"list": "name",
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
            print "Invalid command\n"
            print "Commands: ",
            for key in cmdargs.keys():
                print key + ",",
            print ""
            sys.exit(2)

        parser = OptionParser(usage="sfi [sfi_options] %s [options] %s" \
                                     % (command, cmdargs[command]))

        # user specifies remote aggregate/sm/component                          
        if command in ("resources", "slices", "create", "delete", "start", "stop", "restart", "get_ticket", "redeem_ticket"):
            parser.add_option("-a", "--aggregate", dest="aggregate",
                             default=None, help="aggregate host")
            parser.add_option("-p", "--port", dest="port",
                             default=AGGREGATE_PORT, help="aggregate port")
            parser.add_option("-c", "--component", dest="component", default=None,
                             help="component hrn")
        
        # registy filter option    
        if command in ("list", "show", "remove"):
            parser.add_option("-t", "--type", dest="type", type="choice",
                            help="type filter ([all]|user|slice|authority|node|aggregate)",
                            choices=("all", "user", "slice", "authority", "node", "aggregate"),
                            default="all")
        # display formats
        if command in ("resources"):
            parser.add_option("-f", "--format", dest="format", type="choice",
                             help="display format ([xml]|dns|ip)", default="xml",
                             choices=("xml", "dns", "ip"))

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
        parser.add_option("-v", "--verbose",
                         action="store_true", dest="verbose", default=False,
                         help="verbose mode")
        parser.add_option("-D", "--debug",
                          action="store_true", dest="debug", default=False,
                          help="Debug (xml-rpc) protocol messages")
        parser.add_option("-p", "--protocol",
                         dest="protocol", default="xmlrpc",
                         help="RPC protocol (xmlrpc or soap)")
        parser.add_option("-k", "--hashrequest",
                         action="store_true", dest="hashrequest", default=False,
                         help="Create a hash of the request that will be authenticated on the server")
        parser.disable_interspersed_args()

        return parser
        
 
    #
    # Establish Connection to SliceMgr and Registry Servers
    #
    def set_servers(self):
       config_file = self.options.sfi_dir + os.sep + "sfi_config"
       try:
          config = Config (config_file)
       except:
          print "Failed to read configuration file", config_file
          print "Make sure to remove the export clauses and to add quotes"
          if not self.options.verbose:
             print "Re-run with -v for more details"
          else:
             traceback.print_exc()
          sys.exit(1)
    
       errors = 0
       # Set SliceMgr URL
       if (self.options.sm is not None):
          sm_url = self.options.sm
       elif hasattr(config, "SFI_SM"):
          sm_url = config.SFI_SM
       else:
          print "You need to set e.g. SFI_SM='http://your.slicemanager.url:12347/' in %s" % config_file
          errors += 1 
    
       # Set Registry URL
       if (self.options.registry is not None):
          reg_url = self.options.registry
       elif hasattr(config, "SFI_REGISTRY"):
          reg_url = config.SFI_REGISTRY
       else:
          print "You need to set e.g. SFI_REGISTRY='http://your.registry.url:12345/' in %s" % config_file
          errors += 1 
          

       # Set user HRN
       if (self.options.user is not None):
          self.user = self.options.user
       elif hasattr(config, "SFI_USER"):
          self.user = config.SFI_USER
       else:
          print "You need to set e.g. SFI_USER='plc.princeton.username' in %s" % config_file
          errors += 1 
    
       # Set authority HRN
       if (self.options.auth is not None):
          self.authority = self.options.auth
       elif hasattr(config, "SFI_AUTH"):
          self.authority = config.SFI_AUTH
       else:
          print "You need to set e.g. SFI_AUTH='plc.princeton' in %s" % config_file
          errors += 1 
    
       if errors:
          sys.exit(1)
    
       if self.options.verbose :
          print "Contacting Slice Manager at:", sm_url
          print "Contacting Registry at:", reg_url
    
       # Get key and certificate
       key_file = self.get_key_file()
       cert_file = self.get_cert_file(key_file)
       self.key = Keypair(filename=key_file) 
       self.key_file = key_file
       self.cert_file = cert_file
       self.cert = Certificate(filename=cert_file) 
       # Establish connection to server(s)
       self.registry = xmlrpcprotocol.get_server(reg_url, key_file, cert_file, self.options.debug)  
       self.slicemgr = xmlrpcprotocol.get_server(sm_url, key_file, cert_file, self.options.debug)

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
       #file = os.path.join(self.options.sfi_dir, get_leaf(self.user) + ".pkey")
       if (os.path.isfile(file)):
          return file
       else:
          print "Key file", file, "does not exist"
          sys.exit(-1)
       return
    
    def get_cert_file(self, key_file):
    
       #file = os.path.join(self.options.sfi_dir, get_leaf(self.user) + ".cert")
       file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".cert")
       if (os.path.isfile(file)):
          return file
       else:
          k = Keypair(filename=key_file)
          cert = Certificate(subject=self.user)
          cert.set_pubkey(k)
          cert.set_issuer(k, self.user)
          cert.sign()
          if self.options.verbose :
             print "Writing self-signed certificate to", file
          cert.save_to_file(file)
          return file

    def get_cached_gid(self, file):
        """
        Return a cached gid    
        """
        gid = None 
        if (os.path.isfile(file)):
            gid = GID(filename=file)
        return gid

    def get_gid(self, opts, args):
        hrn = None
        if args:
            hrn = args[0]
        gid = self._get_gid(hrn)
        print gid.save_to_string(save_parents=True)
        return gid

    def _get_gid(self, hrn=None):
        if not hrn:
            hrn = self.user
 
        gidfile = os.path.join(self.options.sfi_dir, hrn + ".gid")
        gid = self.get_cached_gid(gidfile)
        if not gid:
            user_cred = self.get_user_cred()
            records = self.registry.Resolve(hrn, user_cred.save_to_string(save_parents=True))
            if not records:
                raise RecordNotFound(args[0])
            gid = GID(string=records[0]['gid'])
            if self.options.verbose:
                print "Writing gid to ", gidfile 
            gid.save_to_file(filename=gidfile)
        return gid   
                
     
    def get_cached_credential(self, file):
        """
        Return a cached credential only if it hasn't expired.
        """
        if (os.path.isfile(file)):
            credential = Credential(filename=file)
            # make sure it isnt expired 
            if not credential.get_lifetime or \
               datetime.datetime.today() < credential.get_lifetime():
                return credential
        return None 
 
    def get_user_cred(self):
        #file = os.path.join(self.options.sfi_dir, get_leaf(self.user) + ".cred")
        file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".cred")
        return self.get_cred(file, 'user', self.user)

    def get_auth_cred(self):
        if not self.authority:
            print "no authority specified. Use -a or set SF_AUTH"
            sys.exit(-1)
        file = os.path.join(self.options.sfi_dir, get_leaf("authority") + ".cred")
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
                cred_str = self.registry.get_self_credential(cert_string, "user", hrn)
            else:
                # bootstrap slice credential from user credential
                user_cred = self.get_user_cred().save_to_string(save_parents=True)
                cred_str = self.registry.get_credential(user_cred, type, hrn)
            
            if not cred_str:
                print "Failed to get %s credential" % (type)
                sys.exit(-1)
                
            cred = Credential(string=cred_str)
            cred.save_to_file(file, save_parents=True)
            if self.options.verbose:
                print "Writing %s credential to %s" %(type, file)

        return cred
 
    
    def get_rspec_file(self, rspec):
       if (os.path.isabs(rspec)):
          file = rspec
       else:
          file = os.path.join(self.options.sfi_dir, rspec)
       if (os.path.isfile(file)):
          return file
       else:
          print "No such rspec file", rspec
          sys.exit(1)
    
    def get_record_file(self, record):
       if (os.path.isabs(record)):
          file = record
       else:
          file = os.path.join(self.options.sfi_dir, record)
       if (os.path.isfile(file)):
          return file
       else:
          print "No such registry record file", record
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

    def get_component_server_from_hrn(self, hrn):
        # direct connection to the nodes component manager interface
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        records = self.registry.Resolve(hrn, user_cred)
        records = filter_records('node', records)
        if not records:
            print "No such component:", opts.component
        record = records[0]
  
        return self.get_server(record['hostname'], CM_PORT, self.key_file, \
                               self.cert_file, self.options.debug)
 
    def get_server(self, host, port, keyfile, certfile, debug):
        """
        Return an instnace of an xmlrpc server connection    
        """
        url = "http://%s:%s" % (host, port)
        return xmlrpcprotocol.get_server(url, keyfile, certfile, debug)

    def get_server_from_opts(self, opts):
        """
        Return instance of an xmlrpc connection to a slice manager, aggregate
        or component server depending on the specified opts
        """
        server = self.slicemgr
        # direct connection to an aggregate
        if hasattr(opts, 'aggregate') and opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, \
                                     self.cert_file, self.options.debug)
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
        getattr(self, command)(cmd_opts, cmd_args)
 
    # list entires in named authority registry
    def list(self, opts, args):
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = args[0]
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
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = args[0]
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
            print "Must specify either --user or --slice <hrn>"
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

        print "delegated credential for", object_hrn, "to", delegee_hrn, "and wrote to", dest_fn
    
    def delegate_cred(self, object_cred, hrn):
        # the gid and hrn of the object we are delegating
        if isinstance(object_cred, str):
            object_cred = Credential(string=object_cred) 
        object_gid = object_cred.get_gid_object()
        object_hrn = object_gid.get_hrn()
    
        if not object_cred.get_privileges().get_all_delegate():
            print "Error: Object credential", object_hrn, "does not have delegate bit set"
            return
    
        # the gid of the user who will be delegated to
        delegee_gid = self._get_gid(hrn)
        delegee_hrn = delegee_gid.get_hrn()
        delegee_gidfile = os.path.join(self.options.sfi_dir, delegee_hrn + ".gid")
        delegee_gid.save_to_file(filename=delegee_gidfile)
        dcred = object_cred.delegate(delegee_gidfile, self.get_key_file())
        return dcred.save_to_string(save_parents=True)
     
    # removed named registry record
    #   - have to first retrieve the record to be removed
    def remove(self, opts, args):
        auth_cred = self.get_auth_cred().save_to_string(save_parents=True)
        hrn = args[0]
        type = opts.type 
        if type in ['all']:
            type = '*'
        return self.registry.Remove(hrn, auth_cred, type)
    
    # add named registry record
    def add(self, opts, args):
        auth_cred = self.get_auth_cred().save_to_string(save_parents=True)
        record_filepath = args[0]
        rec_file = self.get_record_file(record_filepath)
        record = load_record_from_file(rec_file).as_dict()
        return self.registry.Register(record, auth_cred)
    
    # update named registry entry
    def update(self, opts, args):
        user_cred = self.get_user_cred()
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
            except ServerException, e:
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
            print cert.get_subject()
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
        server = self.get_server_from_opts(opts)
        
        print server.GetVersion()

    # list instantiated slices
    def slices(self, opts, args):
        """
        list instantiated slices
        """
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        server = self.get_server_from_opts(opts)
        results = server.ListSlices([user_cred])
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
     
        delegated_cred = self.delegate_cred(cred, get_authority(self.authority))
        creds = [cred, delegated_cred] 
        #creds = [delegated_cred] 
        result = server.ListResources(creds, call_options)
        format = opts.format
        display_rspec(result, format)
        if (opts.file is not None):
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
        rspec_file = self.get_rspec_file(args[1])
        rspec = open(rspec_file).read()
        server = self.get_server_from_opts(opts)
        result =  server.CreateSliver(slice_urn, [slice_cred], rspec, [])
        print result
        return result

    # get a ticket for the specified slice
    def get_ticket(self, opts, args):
        slice_hrn, rspec_path = args[0], args[1]
        slice_urn = hrn_to_urn(slice_hrn, 'slice')
        user_cred = self.get_user_cred()
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        rspec_file = self.get_rspec_file(rspec_path) 
        rspec = open(rspec_file).read()
        server = self.get_server_from_opts(opts)
        ticket_string = server.GetTicket(slice_urn, [slice_cred], rspec, [])
        file = os.path.join(self.options.sfi_dir, get_leaf(slice_hrn) + ".ticket")
        print "writing ticket to ", file        
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
                print "Calling redeem_ticket at %(hostname)s " % locals(),
                server = self.get_server(hostname, CM_PORT, self.key_file, \
                                         self.cert_file, self.options.debug)
                server.RedeemTicket(ticket.save_to_string(save_parents=True), slice_cred)
                print "Success"
            except socket.gaierror:
                print "Failed:",
                print "Componet Manager not accepting requests" 
            except Exception, e:
                print "Failed:", e.message
        return
 
    # delete named slice
    def delete(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        server = self.get_server_from_opts(opts)
        return server.DeleteSliver(slice_urn, [slice_cred])
    
    # start named slice
    def start(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        server = self.get_server_from_opts(opts)
        return server.Start(slice_urn, [slice_cred])
    
    # stop named slice
    def stop(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        server = self.get_server_from_opts(opts)
        return server.Stop(slice_urn, [slice_cred])
    
    # reset named slice
    def reset(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        server = self.get_server_from_opts(opts)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        return server.reset_slice(slice_cred, slice_urn)

    def renew(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        server = self.get_server_from_opts(opts)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        time = args[1]
        return server.RenewSliver(slice_urn, [slice_cred], time)


    def status(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        server = self.get_server_from_opts(opts)
        print server.SliverStatus(slice_urn, [slice_cred])


    def shutdown(self, opts, args):
        slice_hrn = args[0]
        slice_urn = hrn_to_urn(slice_hrn, 'slice') 
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        server = self.get_server_from_opts(opts)
        return server.Shutdown(slice_urn, [slice_cred])         
    
    #
    # Main: parse arguments and dispatch to command
    #
    def main(self):
        parser = self.create_parser()
        (options, args) = parser.parse_args()
        self.options = options
   
        if options.hashrequest:
            self.hashrequest = True
 
        if len(args) <= 0:
            print "No command given. Use -h for help."
            return - 1
    
        command = args[0]
        (cmd_opts, cmd_args) = self.create_cmd_parser(command).parse_args(args[1:])
        if self.options.verbose :
            print "Registry %s, sm %s, dir %s, user %s, auth %s" % (options.registry, options.sm,
                                                                   options.sfi_dir, options.user,
                                                                   options.auth)
            print "Command %s" % command
            if command in ("resources"):
                print "resources cmd_opts %s" % cmd_opts.format
            elif command in ("list", "show", "remove"):
                print "cmd_opts.type %s" % cmd_opts.type
            print "cmd_args %s" % cmd_args
    
        self.set_servers()
    
        try:
            self.dispatch(command, cmd_opts, cmd_args)
        except KeyError:
            raise 
            print "Command not found:", command
            sys.exit(1)
    
        return
    
if __name__ == "__main__":
   Sfi().main()
