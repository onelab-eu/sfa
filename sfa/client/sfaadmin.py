#!/usr/bin/python
import os
import sys
import copy
from pprint import pformat, PrettyPrinter
from optparse import OptionParser

from sfa.generic import Generic
from sfa.util.xrn import Xrn
from sfa.storage.record import Record 

from sfa.trust.hierarchy import Hierarchy
from sfa.trust.gid import GID
from sfa.trust.certificate import convert_public_key

from sfa.client.common import optparse_listvalue_callback, optparse_dictvalue_callback, terminal_render, filter_records
from sfa.client.candidates import Candidates
from sfa.client.sfi import save_records_to_file

pprinter = PrettyPrinter(indent=4)

try:
    help_basedir=Hierarchy().basedir
except:
    help_basedir='*unable to locate Hierarchy().basedir'

def add_options(*args, **kwargs):
    def _decorator(func):
        func.__dict__.setdefault('add_options', []).insert(0, (args, kwargs))
        return func
    return _decorator

class Commands(object):
    def _get_commands(self):
        command_names = []
        for attrib in dir(self):
            if callable(getattr(self, attrib)) and not attrib.startswith('_'):
                command_names.append(attrib)
        return command_names


class RegistryCommands(Commands):
    def __init__(self, *args, **kwds):
        self.api= Generic.the_flavour().make_api(interface='registry')
 
    def version(self):
        """Display the Registry version""" 
        version = self.api.manager.GetVersion(self.api, {})
        pprinter.pprint(version)

    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='authority to list (hrn/urn - mandatory)') 
    @add_options('-t', '--type', dest='type', metavar='<type>', help='object type', default='all') 
    @add_options('-r', '--recursive', dest='recursive', metavar='<recursive>', help='list all child records', 
                 action='store_true', default=False)
    @add_options('-v', '--verbose', dest='verbose', action='store_true', default=False)
    def list(self, xrn, type=None, recursive=False, verbose=False):
        """List names registered at a given authority - possibly filtered by type"""
        xrn = Xrn(xrn, type) 
        options_dict = {'recursive': recursive}
        records = self.api.manager.List(self.api, xrn.get_hrn(), options=options_dict)
        list = filter_records(type, records)
        # terminal_render expects an options object
        class Options: pass
        options=Options()
        options.verbose=verbose
        terminal_render (list, options)


    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn (mandatory)') 
    @add_options('-t', '--type', dest='type', metavar='<type>', help='object type', default=None) 
    @add_options('-o', '--outfile', dest='outfile', metavar='<outfile>', help='save record to file') 
    @add_options('-f', '--format', dest='format', metavar='<display>', type='choice', 
                 choices=('text', 'xml', 'simple'), help='display record in different formats') 
    def show(self, xrn, type=None, format=None, outfile=None):
        """Display details for a registered object"""
        records = self.api.manager.Resolve(self.api, xrn, type, details=True)
        for record in records:
            sfa_record = Record(dict=record)
            sfa_record.dump(format) 
        if outfile:
            save_records_to_file(outfile, records)  


    def _record_dict(self, xrn, type, email, key, 
                     slices, researchers, pis, 
                     url, description, extras):
        record_dict = {}
        if xrn:
            if type:
                xrn = Xrn(xrn, type)
            else:
                xrn = Xrn(xrn)
            record_dict['urn'] = xrn.get_urn()
            record_dict['hrn'] = xrn.get_hrn()
            record_dict['type'] = xrn.get_type()
        if url:
            record_dict['url'] = url
        if description:
            record_dict['description'] = description
        if key:
            try:
                pubkey = open(key, 'r').read()
            except IOError:
                pubkey = key
            record_dict['reg-keys'] = [pubkey]
        if slices:
            record_dict['slices'] = slices
        if researchers:
            record_dict['reg-researchers'] = researchers
        if email:
            record_dict['email'] = email
        if pis:
            record_dict['reg-pis'] = pis
        if extras:
            record_dict.update(extras)
        return record_dict


    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn', default=None)
    @add_options('-t', '--type', dest='type', metavar='<type>', help='object type (mandatory)',)
    @add_options('-a', '--all', dest='all', metavar='<all>', action='store_true', default=False, help='check all users GID')
    @add_options('-v', '--verbose', dest='verbose', metavar='<verbose>', action='store_true', default=False, help='verbose mode: display user\'s hrn ')
    def check_gid(self, xrn=None, type=None, all=None, verbose=None):
        """Check the correspondance between the GID and the PubKey"""

        # db records
        from sfa.storage.model import RegRecord
        db_query = self.api.dbsession().query(RegRecord).filter_by(type=type)
        if xrn and not all:
            hrn = Xrn(xrn).get_hrn()
            db_query = db_query.filter_by(hrn=hrn)
        elif all and xrn:
            print "Use either -a or -x <xrn>, not both !!!"
            sys.exit(1)
        elif not all and not xrn:
            print "Use either -a or -x <xrn>, one of them is mandatory !!!"
            sys.exit(1)

        records = db_query.all()
        if not records:
            print "No Record found"
            sys.exit(1)

        OK = []
        NOK = []
        ERROR = []
        NOKEY = []
        for record in records:
             # get the pubkey stored in SFA DB
             if record.reg_keys:
                 db_pubkey_str = record.reg_keys[0].key
                 try:
                   db_pubkey_obj = convert_public_key(db_pubkey_str)
                 except:
                   ERROR.append(record.hrn)
                   continue
             else:
                 NOKEY.append(record.hrn)
                 continue

             # get the pubkey from the gid
             gid_str = record.gid
             gid_obj = GID(string = gid_str)
             gid_pubkey_obj = gid_obj.get_pubkey()

             # Check if gid_pubkey_obj and db_pubkey_obj are the same
             check = gid_pubkey_obj.is_same(db_pubkey_obj)
             if check :
                 OK.append(record.hrn)
             else:
                 NOK.append(record.hrn)

        if not verbose:
            print "Users NOT having a PubKey: %s\n\
Users having a non RSA PubKey: %s\n\
Users having a GID/PubKey correpondence OK: %s\n\
Users having a GID/PubKey correpondence Not OK: %s\n"%(len(NOKEY), len(ERROR), len(OK), len(NOK))
        else:
            print "Users NOT having a PubKey: %s and are: \n%s\n\n\
Users having a non RSA PubKey: %s and are: \n%s\n\n\
Users having a GID/PubKey correpondence OK: %s and are: \n%s\n\n\
Users having a GID/PubKey correpondence NOT OK: %s and are: \n%s\n\n"%(len(NOKEY),NOKEY, len(ERROR), ERROR, len(OK), OK, len(NOK), NOK)



    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn (mandatory)') 
    @add_options('-t', '--type', dest='type', metavar='<type>', help='object type', default=None) 
    @add_options('-e', '--email', dest='email', default="",
                 help="email (mandatory for users)")
    @add_options('-u', '--url', dest='url', metavar='<url>', default=None,
                 help="URL, useful for slices")
    @add_options('-d', '--description', dest='description', metavar='<description>', 
                 help='Description, useful for slices', default=None)
    @add_options('-k', '--key', dest='key', metavar='<key>', help='public key string or file', 
                 default=None)
    @add_options('-s', '--slices', dest='slices', metavar='<slices>', help='Set/replace slice xrns', 
                 default='', type="str", action='callback', callback=optparse_listvalue_callback)
    @add_options('-r', '--researchers', dest='researchers', metavar='<researchers>', help='Set/replace slice researchers', 
                 default='', type="str", action='callback', callback=optparse_listvalue_callback)
    @add_options('-p', '--pis', dest='pis', metavar='<PIs>', 
                 help='Set/replace Principal Investigators/Project Managers', 
                 default='', type="str", action='callback', callback=optparse_listvalue_callback)
    @add_options('-X','--extra',dest='extras',default={},type='str',metavar="<EXTRA_ASSIGNS>", 
                 action="callback", callback=optparse_dictvalue_callback, nargs=1, 
                 help="set extra/testbed-dependent flags, e.g. --extra enabled=true")
    def register(self, xrn, type=None, email='', key=None, 
                 slices='', pis='', researchers='',
                 url=None, description=None, extras={}):
        """Create a new Registry record"""
        record_dict = self._record_dict(xrn=xrn, type=type, email=email, key=key, 
                                        slices=slices, researchers=researchers, pis=pis,
                                        url=url, description=description, extras=extras)
        self.api.manager.Register(self.api, record_dict)         


    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn (mandatory)')
    @add_options('-t', '--type', dest='type', metavar='<type>', help='object type', default=None)
    @add_options('-u', '--url', dest='url', metavar='<url>', help='URL', default=None)
    @add_options('-d', '--description', dest='description', metavar='<description>',
                 help='Description', default=None)
    @add_options('-k', '--key', dest='key', metavar='<key>', help='public key string or file',
                 default=None)
    @add_options('-s', '--slices', dest='slices', metavar='<slices>', help='Set/replace slice xrns',
                 default='', type="str", action='callback', callback=optparse_listvalue_callback)
    @add_options('-r', '--researchers', dest='researchers', metavar='<researchers>', help='Set/replace slice researchers',
                 default='', type="str", action='callback', callback=optparse_listvalue_callback)
    @add_options('-p', '--pis', dest='pis', metavar='<PIs>',
                 help='Set/replace Principal Investigators/Project Managers',
                 default='', type="str", action='callback', callback=optparse_listvalue_callback)
    @add_options('-X','--extra',dest='extras',default={},type='str',metavar="<EXTRA_ASSIGNS>", 
                 action="callback", callback=optparse_dictvalue_callback, nargs=1, 
                 help="set extra/testbed-dependent flags, e.g. --extra enabled=true")
    def update(self, xrn, type=None, email='', key=None, 
               slices='', pis='', researchers='',
               url=None, description=None, extras={}):
        """Update an existing Registry record""" 
        record_dict = self._record_dict(xrn=xrn, type=type, email=email, key=key, 
                                        slices=slices, researchers=researchers, pis=pis,
                                        url=url, description=description, extras=extras)
        self.api.manager.Update(self.api, record_dict)
        
    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn (mandatory)') 
    @add_options('-t', '--type', dest='type', metavar='<type>', help='object type', default=None) 
    def remove(self, xrn, type=None):
        """Remove given object from the registry"""
        xrn = Xrn(xrn, type)
        self.api.manager.Remove(self.api, xrn)            


    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn (mandatory)') 
    @add_options('-t', '--type', dest='type', metavar='<type>', help='object type', default=None) 
    def credential(self, xrn, type=None):
        """Invoke GetCredential"""
        cred = self.api.manager.GetCredential(self.api, xrn, type, self.api.hrn)
        print cred
   

    def import_registry(self):
        """Run the importer"""
        from sfa.importer import Importer
        importer = Importer()
        importer.run()

    def sync_db(self):
        """Initialize or upgrade the db"""
        from sfa.storage.dbschema import DBSchema
        dbschema=DBSchema()
        dbschema.init_or_upgrade()
    
    @add_options('-a', '--all', dest='all', metavar='<all>', action='store_true', default=False,
                 help='Remove all registry records and all files in %s area' % help_basedir)
    @add_options('-c', '--certs', dest='certs', metavar='<certs>', action='store_true', default=False,
                 help='Remove all cached certs/gids found in %s' % help_basedir )
    @add_options('-0', '--no-reinit', dest='reinit', metavar='<reinit>', action='store_false', default=True,
                 help='Prevents new DB schema from being installed after cleanup')
    def nuke(self, all=False, certs=False, reinit=True):
        """Cleanup local registry DB, plus various additional filesystem cleanups optionally"""
        from sfa.storage.dbschema import DBSchema
        from sfa.util.sfalogging import _SfaLogger
        logger = _SfaLogger(logfile='/var/log/sfa_import.log', loggername='importlog')
        logger.setLevelFromOptVerbose(self.api.config.SFA_API_LOGLEVEL)
        logger.info("Purging SFA records from database")
        dbschema=DBSchema()
        dbschema.nuke()

        # for convenience we re-create the schema here, so there's no need for an explicit
        # service sfa restart
        # however in some (upgrade) scenarios this might be wrong
        if reinit:
            logger.info("re-creating empty schema")
            dbschema.init_or_upgrade()

        # remove the server certificate and all gids found in /var/lib/sfa/authorities
        if certs:
            logger.info("Purging cached certificates")
            for (dir, _, files) in os.walk('/var/lib/sfa/authorities'):
                for file in files:
                    if file.endswith('.gid') or file == 'server.cert':
                        path=dir+os.sep+file
                        os.unlink(path)

        # just remove all files that do not match 'server.key' or 'server.cert'
        if all:
            logger.info("Purging registry filesystem cache")
            preserved_files = [ 'server.key', 'server.cert']
            for (dir,_,files) in os.walk(Hierarchy().basedir):
                for file in files:
                    if file in preserved_files: continue
                    path=dir+os.sep+file
                    os.unlink(path)
        
    
class CertCommands(Commands):

    def __init__(self, *args, **kwds):
        self.api= Generic.the_flavour().make_api(interface='registry')
    
    def import_gid(self, xrn):
        pass

    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn (mandatory)')
    @add_options('-t', '--type', dest='type', metavar='<type>', help='object type', default=None)
    @add_options('-o', '--outfile', dest='outfile', metavar='<outfile>', help='output file', default=None)
    def export(self, xrn, type=None, outfile=None):
        """Fetch an object's GID from the Registry"""  
        from sfa.storage.model import RegRecord
        hrn = Xrn(xrn).get_hrn()
        request=self.api.dbsession().query(RegRecord).filter_by(hrn=hrn)
        if type: request = request.filter_by(type=type)
        record=request.first()
        if record:
            gid = GID(string=record.gid)
        else:
            # check the authorities hierarchy
            hierarchy = Hierarchy()
            try:
                auth_info = hierarchy.get_auth_info(hrn)
                gid = auth_info.gid_object
            except:
                print "Record: %s not found" % hrn
                sys.exit(1)
        # save to file
        if not outfile:
            outfile = os.path.abspath('./%s.gid' % gid.get_hrn())
        gid.save_to_file(outfile, save_parents=True)
        
    @add_options('-g', '--gidfile', dest='gid', metavar='<gid>', help='path of gid file to display (mandatory)') 
    def display(self, gidfile):
        """Print contents of a GID file"""
        gid_path = os.path.abspath(gidfile)
        if not gid_path or not os.path.isfile(gid_path):
            print "No such gid file: %s" % gidfile
            sys.exit(1)
        gid = GID(filename=gid_path)
        gid.dump(dump_parents=True)
    

class AggregateCommands(Commands):

    def __init__(self, *args, **kwds):
        self.api= Generic.the_flavour().make_api(interface='aggregate')
   
    def version(self):
        """Display the Aggregate version"""
        version = self.api.manager.GetVersion(self.api, {})
        pprinter.pprint(version)

    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn (mandatory)') 
    def status(self, xrn):
        """Retrieve the status of the slivers belonging to the named slice (Status)"""
        urns = [Xrn(xrn, 'slice').get_urn()]
        status = self.api.manager.Status(self.api, urns, [], {})
        pprinter.pprint(status)
 
    @add_options('-r', '--rspec-version', dest='rspec_version', metavar='<rspec_version>', 
                 default='GENI', help='version/format of the resulting rspec response')  
    def resources(self, rspec_version='GENI'):
        """Display the available resources at an aggregate"""  
        options = {'geni_rspec_version': rspec_version}
        print options
        resources = self.api.manager.ListResources(self.api, [], options)
        print resources
        

    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='slice hrn/urn (mandatory)')
    @add_options('-r', '--rspec', dest='rspec', metavar='<rspec>', help='rspec file (mandatory)')
    def allocate(self, xrn, rspec):
        """Allocate slivers"""
        xrn = Xrn(xrn, 'slice')
        slice_urn=xrn.get_urn()
        rspec_string = open(rspec).read()
        options={}
        manifest = self.api.manager.Allocate(self.api, slice_urn, [], rspec_string, options)
        print manifest


    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='slice hrn/urn (mandatory)')
    def provision(self, xrn):
        """Provision slivers"""
        xrn = Xrn(xrn, 'slice')
        slice_urn=xrn.get_urn()
        options={}
        manifest = self.api.manager.provision(self.api, [slice_urn], [], options)
        print manifest



    @add_options('-x', '--xrn', dest='xrn', metavar='<xrn>', help='slice hrn/urn (mandatory)')
    def delete(self, xrn):
        """Delete slivers""" 
        self.api.manager.Delete(self.api, [xrn], [], {})
 



class SliceManagerCommands(AggregateCommands):
    
    def __init__(self, *args, **kwds):
        self.api= Generic.the_flavour().make_api(interface='slicemgr')


class SfaAdmin:

    CATEGORIES = {'certificate': CertCommands,
                  'registry': RegistryCommands,
                  'aggregate': AggregateCommands,
                  'slicemgr': SliceManagerCommands}

    # returns (name,class) or (None,None)
    def find_category (self, input):
        full_name=Candidates (SfaAdmin.CATEGORIES.keys()).only_match(input)
        if not full_name: return (None,None)
        return (full_name,SfaAdmin.CATEGORIES[full_name])

    def summary_usage (self, category=None):
        print "Usage:", self.script_name + " category command [<options>]"
        if category and category in SfaAdmin.CATEGORIES: 
            categories=[category]
        else:
            categories=SfaAdmin.CATEGORIES
        for c in categories:
            cls=SfaAdmin.CATEGORIES[c]
            print "==================== category=%s"%c
            names=cls.__dict__.keys()
            names.sort()
            for name in names:
                method=cls.__dict__[name]
                if name.startswith('_'): continue
                margin=15
                format="%%-%ds"%margin
                print "%-15s"%name,
                doc=getattr(method,'__doc__',None)
                if not doc: 
                    print "<missing __doc__>"
                    continue
                lines=[line.strip() for line in doc.split("\n")]
                line1=lines.pop(0)
                print line1
                for extra_line in lines: print margin*" ",extra_line
        sys.exit(2)

    def main(self):
        argv = copy.deepcopy(sys.argv)
        self.script_name = argv.pop(0)
        # ensure category is specified    
        if len(argv) < 1:
            self.summary_usage()

        # ensure category is valid
        category_input = argv.pop(0)
        (category_name, category_class) = self.find_category (category_input)
        if not category_name or not category_class:
            self.summary_usage(category_name)

        usage = "%%prog %s command [options]" % (category_name)
        parser = OptionParser(usage=usage)
    
        # ensure command is valid      
        category_instance = category_class()
        commands = category_instance._get_commands()
        if len(argv) < 1:
            # xxx what is this about ?
            command_name = '__call__'
        else:
            command_input = argv.pop(0)
            command_name = Candidates (commands).only_match (command_input)
    
        if command_name and hasattr(category_instance, command_name):
            command = getattr(category_instance, command_name)
        else:
            self.summary_usage(category_name)

        # ensure options are valid
        usage = "%%prog %s %s [options]" % (category_name, command_name)
        parser = OptionParser(usage=usage)
        for args, kwdargs in getattr(command, 'add_options', []):
            parser.add_option(*args, **kwdargs)
        (opts, cmd_args) = parser.parse_args(argv)
        cmd_kwds = vars(opts)

        # dont overrride meth
        for k, v in cmd_kwds.items():
            if v is None:
                del cmd_kwds[k]

        # execute command
        try:
            #print "invoking %s *=%s **=%s"%(command.__name__,cmd_args, cmd_kwds)
            command(*cmd_args, **cmd_kwds)
            sys.exit(0)
        except TypeError:
            print "Possible wrong number of arguments supplied"
            #import traceback
            #traceback.print_exc()
            print command.__doc__
            parser.print_help()
            sys.exit(1)
            #raise
        except Exception:
            print "Command failed, please check log for more info"
            raise
            sys.exit(1)
