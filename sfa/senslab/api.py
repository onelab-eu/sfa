#
# SFA XML-RPC and SOAP interfaces
#

import sys
import os
import traceback
import string
import datetime
import xmlrpclib

from sfa.util.faults import *
from sfa.util.api import *
from sfa.util.config import *
from sfa.util.sfalogging import logger
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
from sfa.trust.auth import Auth
from sfa.trust.rights import Right, Rights, determine_rights
from sfa.trust.credential import Credential,Keypair
from sfa.trust.certificate import Certificate
from sfa.util.xrn import get_authority, hrn_to_urn
from sfa.util.plxrn import hostname_to_hrn, hrn_to_pl_slicename, hrn_to_pl_slicename, slicename_to_hrn
from sfa.util.nodemanager import NodeManager

from sfa.senslab.OARrestapi import *
from sfa.senslab.SenslabImportUsers import *

try:
    from collections import defaultdict
except:
    class defaultdict(dict):
        def __init__(self, default_factory=None, *a, **kw):
            if (default_factory is not None and
                not hasattr(default_factory, '__call__')):
                raise TypeError('first argument must be callable')
            dict.__init__(self, *a, **kw)
            self.default_factory = default_factory
        def __getitem__(self, key):
            try:
                return dict.__getitem__(self, key)
            except KeyError:
                return self.__missing__(key)
        def __missing__(self, key):
            if self.default_factory is None:
                raise KeyError(key)
            self[key] = value = self.default_factory()
            return value
        def __reduce__(self):
            if self.default_factory is None:
                args = tuple()
            else:
                args = self.default_factory,
            return type(self), args, None, None, self.items()
        def copy(self):
            return self.__copy__()
        def __copy__(self):
            return type(self)(self.default_factory, self)
        def __deepcopy__(self, memo):
            import copy
            return type(self)(self.default_factory,
                              copy.deepcopy(self.items()))
        def __repr__(self):
            return 'defaultdict(%s, %s)' % (self.default_factory,
                                            dict.__repr__(self))
## end of http://code.activestate.com/recipes/523034/ }}}

def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
   # print>>sys.stderr, " \r\n \t\t 1list_to_dict : rec %s  \r\n \t\t list_to_dict key %s" %(recs,key)   
    keys = [rec[key] for rec in recs]
    print>>sys.stderr, " \r\n \t\t list_to_dict : rec %s  \r\n \t\t list_to_dict keys %s" %(recs,keys)   
    return dict(zip(keys, recs))

class SfaAPI(BaseAPI):

    # flat list of method names
    import sfa.methods
    methods = sfa.methods.all
    
    def __init__(self, config = "/etc/sfa/sfa_config.py", encoding = "utf-8", 
                 methods='sfa.methods', peer_cert = None, interface = None, 
                key_file = None, cert_file = None, cache = None):
        BaseAPI.__init__(self, config=config, encoding=encoding, methods=methods, \
                         peer_cert=peer_cert, interface=interface, key_file=key_file, \
                         cert_file=cert_file, cache=cache)
 
        self.encoding = encoding
        from sfa.util.table import SfaTable
        self.SfaTable = SfaTable
        # Better just be documenting the API
        if config is None:
            return
	print >>sys.stderr, "\r\n_____________ SFA SENSLAB API \r\n" 
        # Load configuration
        self.config = Config(config)
        self.auth = Auth(peer_cert)
        self.interface = interface
        self.key_file = key_file
        self.key = Keypair(filename=self.key_file)
        self.cert_file = cert_file
        self.cert = Certificate(filename=self.cert_file)
        self.credential = None
        # Initialize the PLC shell only if SFA wraps a myPLC
        rspec_type = self.config.get_aggregate_type()
	self.oar = OARapi()
	self.users = SenslabImportUsers()
        self.hrn = self.config.SFA_INTERFACE_HRN
        self.time_format = "%Y-%m-%d %H:%M:%S"
        #self.logger=sfa_logger()
	print >>sys.stderr, "\r\n \t\t___________PLC/API.PY  __init__ STOP ",self.interface #dir(self)
	
	
    #def getPLCShell(self):
        #self.plauth = {'Username': self.config.SFA_PLC_USER,
                       #'AuthMethod': 'password',
                       #'AuthString': self.config.SFA_PLC_PASSWORD}
        #try:
	    #print >>sys.stderr, "\r\n \t\t___________PLC/API.PY  getPLCShell "
            #sys.path.append(os.path.dirname(os.path.realpath("/usr/bin/plcsh")))
            #self.plshell_type = 'direct'
            #import PLC.Shell
            #shell = PLC.Shell.Shell(globals = globals())
	    #print >>sys.stderr, "\r\n \t\t____tryshell %s \r\n  type %s \r\n %s"%(shell, type(shell), dir(shell))
	    
        #except:
            #self.plshell_type = 'xmlrpc'  
	    #print >>sys.stderr, "\r\n \t\t___________PLC/API.PY  getPLCShell  xmlrpc"
            #url = self.config.SFA_PLC_URL
            #shell = xmlrpclib.Server(url, verbose = 0, allow_none = True)
        
        #return shell

    def getCredential(self):
        """
        Return a valid credential for this interface. 
        """
        type = 'authority'
        path = self.config.SFA_DATA_DIR
        filename = ".".join([self.interface, self.hrn, type, "cred"])
        cred_filename = path + os.sep + filename
	print>>sys.stderr, "|\r\n \r\n API.pPY getCredential  cred_filename %s" %(cred_filename)
        cred = None
        if os.path.isfile(cred_filename):
            cred = Credential(filename = cred_filename)
            # make sure cred isnt expired
            if not cred.get_expiration or \
               datetime.datetime.today() < cred.get_expiration():    
                return cred.save_to_string(save_parents=True)

        # get a new credential
        if self.interface in ['registry']:
            cred =  self.__getCredentialRaw()
        else:
            cred =  self.__getCredential()
        cred.save_to_file(cred_filename, save_parents=True)

        return cred.save_to_string(save_parents=True)


    def getDelegatedCredential(self, creds):
        """
        Attempt to find a credential delegated to us in
        the specified list of creds.
        """
       if creds and not isinstance(creds, list): 
            creds = [creds]
        delegated_creds = filter_creds_by_caller(creds, [self.hrn, self.hrn + '.slicemanager'])
        if not delegated_creds:
            return None
        return delegated_creds[0]
 
    def __getCredential(self):
        """ 
        Get our credential from a remote registry 
        """
        from sfa.server.registry import Registries
        registries = Registries(self)
        registry = registries[self.hrn]
        cert_string=self.cert.save_to_string(save_parents=True)
        # get self credential
        self_cred = registry.GetSelfCredential(cert_string, self.hrn, 'authority')
        # get credential
        cred = registry.GetCredential(self_cred, self.hrn, 'authority')
        return Credential(string=cred)

    def __getCredentialRaw(self):
        """
        Get our current credential directly from the local registry.
        """

        hrn = self.hrn
        auth_hrn = self.auth.get_authority(hrn)
    
        # is this a root or sub authority
        if not auth_hrn or hrn == self.config.SFA_INTERFACE_HRN:
            auth_hrn = hrn
        auth_info = self.auth.get_auth_info(auth_hrn)
        table = self.SfaTable()
        records = table.findObjects(hrn)
        if not records:
            raise RecordNotFound
        record = records[0]
        type = record['type']
        object_gid = record.get_gid_object()
        new_cred = Credential(subject = object_gid.get_subject())
        new_cred.set_gid_caller(object_gid)
        new_cred.set_gid_object(object_gid)
        new_cred.set_issuer_keys(auth_info.get_privkey_filename(), auth_info.get_gid_filename())
        
        r1 = determine_rights(type, hrn)
        new_cred.set_privileges(r1)
        new_cred.encode()
        new_cred.sign()

        return new_cred
   

    def loadCredential (self):
        """
        Attempt to load credential from file if it exists. If it doesnt get
        credential from registry.
        """

        # see if this file exists
        # XX This is really the aggregate's credential. Using this is easier than getting
        # the registry's credential from iteslf (ssl errors).   
        ma_cred_filename = self.config.SFA_DATA_DIR + os.sep + self.interface + self.hrn + ".ma.cred"
        try:
            self.credential = Credential(filename = ma_cred_filename)
        except IOError:
            self.credential = self.getCredentialFromRegistry()

    ##
    # Convert SFA fields to PLC fields for use when registering up updating
    # registry record in the PLC database
    #
    # @param type type of record (user, slice, ...)
    # @param hrn human readable name
    # @param sfa_fields dictionary of SFA fields
    # @param pl_fields dictionary of PLC fields (output)

    def sfa_fields_to_pl_fields(self, type, hrn, record):

        def convert_ints(tmpdict, int_fields):
            for field in int_fields:
                if field in tmpdict:
                    tmpdict[field] = int(tmpdict[field])

        pl_record = {}
        #for field in record:
        #    pl_record[field] = record[field]
 
        if type == "slice":
            if not "instantiation" in pl_record:
                pl_record["instantiation"] = "plc-instantiated"
            pl_record["name"] = hrn_to_pl_slicename(hrn)
	    if "url" in record:
               pl_record["url"] = record["url"]
	    if "description" in record:
	        pl_record["description"] = record["description"]
	    if "expires" in record:
	        pl_record["expires"] = int(record["expires"])

        elif type == "node":
            if not "hostname" in pl_record:
                if not "hostname" in record:
                    raise MissingSfaInfo("hostname")
                pl_record["hostname"] = record["hostname"]
            if not "model" in pl_record:
                pl_record["model"] = "geni"

        elif type == "authority":
            pl_record["login_base"] = hrn_to_pl_login_base(hrn)

            if not "name" in pl_record:
                pl_record["name"] = hrn

            if not "abbreviated_name" in pl_record:
                pl_record["abbreviated_name"] = hrn

            if not "enabled" in pl_record:
                pl_record["enabled"] = True

            if not "is_public" in pl_record:
                pl_record["is_public"] = True

        return pl_record

    def fill_record_pl_info(self, records):
        """
        Fill in the planetlab specific fields of a SFA record. This
        involves calling the appropriate PLC method to retrieve the 
        database record for the object.
        
        PLC data is filled into the pl_info field of the record.
    
        @param record: record to fill in field (in/out param)     
        """
        # get ids by type
	print>>sys.stderr, "\r\n \r\rn \t\t >>>>>>>>>>fill_record_pl_info  records %s : "%(records)
        node_ids, site_ids, slice_ids = [], [], [] 
        person_ids, key_ids = [], []
        type_map = {'node': node_ids, 'authority': site_ids,
                    'slice': slice_ids, 'user': person_ids}
                  
        for record in records:
            for type in type_map:
		#print>>sys.stderr, "\r\n \t\t \t fill_record_pl_info : type %s. record['pointer'] %s "%(type,record['pointer'])   
                if type == record['type']:
                    type_map[type].append(record['pointer'])
	print>>sys.stderr, "\r\n \t\t \t fill_record_pl_info : records %s... \r\n \t\t \t fill_record_pl_info : type_map   %s"%(records,type_map)
        # get pl records
        nodes, sites, slices, persons, keys = {}, {}, {}, {}, {}
        if node_ids:
            node_list = self.oar.GetNodes( node_ids)
	    #print>>sys.stderr, " \r\n \t\t\t BEFORE LIST_TO_DICT_NODES node_ids : %s" %(node_ids)
            nodes = list_to_dict(node_list, 'node_id')
        if site_ids:
            site_list = self.oar.GetSites( site_ids)
            sites = list_to_dict(site_list, 'site_id')
	    #print>>sys.stderr, " \r\n \t\t\t  site_ids %s sites  : %s" %(site_ids,sites)	    
        if slice_ids:
            slice_list = self.users.GetSlices( slice_ids)
            slices = list_to_dict(slice_list, 'slice_id')
        if person_ids:
            #print>>sys.stderr, " \r\n \t\t \t fill_record_pl_info BEFORE GetPersons  person_ids: %s" %(person_ids)
            person_list = self.users.GetPersons( person_ids)
            persons = list_to_dict(person_list, 'person_id')
	    print>>sys.stderr, "\r\n  fill_record_pl_info persons %s \r\n \t\t person_ids %s " %(persons, person_ids) 
            for person in persons:
                key_ids.extend(persons[person]['key_ids'])
		print>>sys.stderr, "\r\n key_ids %s " %(key_ids)

        pl_records = {'node': nodes, 'authority': sites,
                      'slice': slices, 'user': persons}

        if key_ids:
            key_list = self.users.GetKeys( key_ids)
            keys = list_to_dict(key_list, 'key_id')
           # print>>sys.stderr, "\r\n  fill_record_pl_info persons %s \r\n \t\t keys %s " %(keys) 
        # fill record info
        for record in records:
            # records with pointer==-1 do not have plc info.
            # for example, the top level authority records which are
            # authorities, but not PL "sites"
            if record['pointer'] == -1:
                continue
           
            for type in pl_records:
                if record['type'] == type:
                    if record['pointer'] in pl_records[type]:
                        record.update(pl_records[type][record['pointer']])
                        break
            # fill in key info 
            if record['type'] == 'user':
		 if 'key_ids' not in record:
                    	print>>sys.stderr, " NO_KEY_IDS fill_record_pl_info key_ids record: %s" %(record)
			logger.info("user record has no 'key_ids' - need to import  ?")
                 else:
			pubkeys = [keys[key_id]['key'] for key_id in record['key_ids'] if key_id in keys] 
			record['keys'] = pubkeys
			
  	print>>sys.stderr, "\r\n \r\rn \t\t <<<<<<<<<<<<<<<<<< fill_record_pl_info  records %s : "%(records)
        # fill in record hrns
        records = self.fill_record_hrns(records)   

        return records

    def fill_record_hrns(self, records):
        """
        convert pl ids to hrns
        """
	print>>sys.stderr, "\r\n \r\rn \t\t \t >>>>>>>>>>>>>>>>>>>>>> fill_record_hrns records %s : "%(records)  
        # get ids
        slice_ids, person_ids, site_ids, node_ids = [], [], [], []
        for record in records:
            print>>sys.stderr, "\r\n \r\rn \t\t \t record %s : "%(record)
            if 'site_id' in record:
                site_ids.append(record['site_id'])
            if 'site_ids' in records:
                site_ids.extend(record['site_ids'])
            if 'person_ids' in record:
                person_ids.extend(record['person_ids'])
            if 'slice_ids' in record:
                slice_ids.extend(record['slice_ids'])
            if 'node_ids' in record:
                node_ids.extend(record['node_ids'])

        # get pl records
        slices, persons, sites, nodes = {}, {}, {}, {}
        if site_ids:
            site_list = self.oar.GetSites( site_ids, ['site_id', 'login_base'])
            sites = list_to_dict(site_list, 'site_id')
	    #print>>sys.stderr, " \r\n \r\n \t\t ____ site_list %s \r\n \t\t____ sites %s " % (site_list,sites)
        if person_ids:
            person_list = self.users.GetPersons( person_ids, ['person_id', 'email'])
	    print>>sys.stderr, " \r\n \r\n   \t\t____ person_lists %s " %(person_list) 
            persons = list_to_dict(person_list, 'person_id')
        if slice_ids:
            slice_list = self.users.GetSlices( slice_ids, ['slice_id', 'name'])
            slices = list_to_dict(slice_list, 'slice_id')       
        if node_ids:
            node_list = self.oar.GetNodes( node_ids, ['node_id', 'hostname'])
            nodes = list_to_dict(node_list, 'node_id')
       
        # convert ids to hrns
        for record in records:
             
            # get all relevant data
            type = record['type']
            pointer = record['pointer']
            auth_hrn = self.hrn
            login_base = ''
            if pointer == -1:
                continue

            #print>>sys.stderr, " \r\n \r\n \t\t fill_record_hrns : sites %s \r\n \t\t record %s " %(sites, record)
            if 'site_id' in record:
                site = sites[record['site_id']]
		#print>>sys.stderr, " \r\n \r\n \t\t \t fill_record_hrns : sites %s \r\n \t\t\t site sites[record['site_id']] %s " %(sites,site)	
                login_base = site['login_base']
                record['site'] = ".".join([auth_hrn, login_base])
            if 'person_ids' in record:
                emails = [persons[person_id]['email'] for person_id in record['person_ids'] \
                          if person_id in  persons]
                usernames = [email.split('@')[0] for email in emails]
                person_hrns = [".".join([auth_hrn, login_base, username]) for username in usernames]
		print>>sys.stderr, " \r\n \r\n \t\t ____ person_hrns : %s " %(person_hrns)
                record['persons'] = person_hrns 
            if 'slice_ids' in record:
                slicenames = [slices[slice_id]['name'] for slice_id in record['slice_ids'] \
                              if slice_id in slices]
                slice_hrns = [slicename_to_hrn(auth_hrn, slicename) for slicename in slicenames]
                record['slices'] = slice_hrns
            if 'node_ids' in record:
                hostnames = [nodes[node_id]['hostname'] for node_id in record['node_ids'] \
                             if node_id in nodes]
                node_hrns = [hostname_to_hrn(auth_hrn, login_base, hostname) for hostname in hostnames]
                record['nodes'] = node_hrns
            if 'site_ids' in record:
                login_bases = [sites[site_id]['login_base'] for site_id in record['site_ids'] \
                               if site_id in sites]
                site_hrns = [".".join([auth_hrn, lbase]) for lbase in login_bases]
                record['sites'] = site_hrns
	print>>sys.stderr, "\r\n \r\rn \t\t \t <<<<<<<<<<<<<<<<<<<<<<<<  fill_record_hrns records %s : "%(records)  
        return records   

    def fill_record_sfa_info(self, records):

        def startswith(prefix, values):
            return [value for value in values if value.startswith(prefix)]
	
   	SenslabUsers = SenslabImportUsers()
        # get person ids
        person_ids = []
        site_ids = []
        for record in records:
            person_ids.extend(record.get("person_ids", []))
            site_ids.extend(record.get("site_ids", [])) 
            if 'site_id' in record:
                site_ids.append(record['site_id']) 
        	
	print>>sys.stderr, "\r\n \r\n _fill_record_sfa_info ___person_ids %s \r\n \t\t site_ids %s " %(person_ids, site_ids)
	
        # get all pis from the sites we've encountered
        # and store them in a dictionary keyed on site_id 
        site_pis = {}
        if site_ids:
            pi_filter = {'|roles': ['pi'], '|site_ids': site_ids} 
            pi_list = SenslabUsers.GetPersons( pi_filter, ['person_id', 'site_ids'])
	    print>>sys.stderr, "\r\n \r\n _fill_record_sfa_info ___ GetPersons ['person_id', 'site_ids'] pi_ilist %s" %(pi_list)

            for pi in pi_list:
                # we will need the pi's hrns also
                person_ids.append(pi['person_id'])
                
                # we also need to keep track of the sites these pis
                # belong to
                for site_id in pi['site_ids']:
                    if site_id in site_pis:
                        site_pis[site_id].append(pi)
                    else:
                        site_pis[site_id] = [pi]
                 
        # get sfa records for all records associated with these records.   
        # we'll replace pl ids (person_ids) with hrns from the sfa records
        # we obtain
        
        # get the sfa records
        table = self.SfaTable()
        person_list, persons = [], {}
        person_list = table.find({'type': 'user', 'pointer': person_ids})
        # create a hrns keyed on the sfa record's pointer.
        # Its possible for  multiple records to have the same pointer so
        # the dict's value will be a list of hrns.
        persons = defaultdict(list)
        for person in person_list:
            persons[person['pointer']].append(person)

        # get the pl records
        pl_person_list, pl_persons = [], {}
        pl_person_list = SenslabUsers.GetPersons(person_ids, ['person_id', 'roles'])
        pl_persons = list_to_dict(pl_person_list, 'person_id')
        print>>sys.stderr, "\r\n \r\n _fill_record_sfa_info ___  _list %s \r\n \t\t SenslabUsers.GetPersons ['person_id', 'roles'] pl_persons %s \r\n records %s" %(pl_person_list, pl_persons,records) 
        # fill sfa info
	
        for record in records:
            # skip records with no pl info (top level authorities)
            if record['pointer'] == -1:
                continue 
            sfa_info = {}
            type = record['type']
            if (type == "slice"):
                # all slice users are researchers
                record['PI'] = []
                record['researcher'] = []
                for person_id in record['person_ids']:
                    hrns = [person['hrn'] for person in persons[person_id]]
                    record['researcher'].extend(hrns)                

                # pis at the slice's site
                pl_pis = site_pis[record['site_id']]
                pi_ids = [pi['person_id'] for pi in pl_pis]
                for person_id in pi_ids:
                    hrns = [person['hrn'] for person in persons[person_id]]
                    record['PI'].extend(hrns)
                record['geni_urn'] = hrn_to_urn(record['hrn'], 'slice')
                record['geni_creator'] = record['PI'] 
                
            elif (type == "authority"):
                record['PI'] = []
                record['operator'] = []
                record['owner'] = []
                for pointer in record['person_ids']:
                    if pointer not in persons or pointer not in pl_persons:
                        # this means there is not sfa or pl record for this user
                        continue   
                    hrns = [person['hrn'] for person in persons[pointer]] 
                    roles = pl_persons[pointer]['roles']   
                    if 'pi' in roles:
                        record['PI'].extend(hrns)
                    if 'tech' in roles:
                        record['operator'].extend(hrns)
                    if 'admin' in roles:
                        record['owner'].extend(hrns)
                    # xxx TODO: OrganizationName
            elif (type == "node"):
                sfa_info['dns'] = record.get("hostname", "")
                # xxx TODO: URI, LatLong, IP, DNS
    
            elif (type == "user"):
                 sfa_info['email'] = record.get("email", "")
                 sfa_info['geni_urn'] = hrn_to_urn(record['hrn'], 'user')
                 sfa_info['geni_certificate'] = record['gid'] 
                # xxx TODO: PostalAddress, Phone
		
            print>>sys.stderr, "\r\n \r\rn \t\t \t <<<<<<<<<<<<<<<<<<<<<<<<  fill_record_sfa_info sfa_info %s  \r\n record %s : "%(sfa_info,record)  
            record.update(sfa_info)

    def fill_record_info(self, records):
        """
        Given a SFA record, fill in the PLC specific and SFA specific
        fields in the record. 
        """
	print >>sys.stderr, "\r\n \t\t fill_record_info %s"%(records)
        if not isinstance(records, list):
            records = [records]
	print >>sys.stderr, "\r\n \t\t BEFORE fill_record_pl_info %s" %(records)	
        self.fill_record_pl_info(records)
	print >>sys.stderr, "\r\n \t\t after fill_record_pl_info %s" %(records)	
        self.fill_record_sfa_info(records)
	print >>sys.stderr, "\r\n \t\t after fill_record_sfa_info"
	
    def update_membership_list(self, oldRecord, record, listName, addFunc, delFunc):
        # get a list of the HRNs tht are members of the old and new records
        if oldRecord:
            oldList = oldRecord.get(listName, [])
        else:
            oldList = []     
        newList = record.get(listName, [])

        # if the lists are the same, then we don't have to update anything
        if (oldList == newList):
            return

        # build a list of the new person ids, by looking up each person to get
        # their pointer
        newIdList = []
        table = self.SfaTable()
        records = table.find({'type': 'user', 'hrn': newList})
        for rec in records:
            newIdList.append(rec['pointer'])

        # build a list of the old person ids from the person_ids field 
        if oldRecord:
            oldIdList = oldRecord.get("person_ids", [])
            containerId = oldRecord.get_pointer()
        else:
            # if oldRecord==None, then we are doing a Register, instead of an
            # update.
            oldIdList = []
            containerId = record.get_pointer()

    # add people who are in the new list, but not the oldList
        for personId in newIdList:
            if not (personId in oldIdList):
                addFunc(self.plauth, personId, containerId)

        # remove people who are in the old list, but not the new list
        for personId in oldIdList:
            if not (personId in newIdList):
                delFunc(self.plauth, personId, containerId)

    def update_membership(self, oldRecord, record):
        if record.type == "slice":
            self.update_membership_list(oldRecord, record, 'researcher',
                                        self.users.AddPersonToSlice,
                                        self.users.DeletePersonFromSlice)
        elif record.type == "authority":
            # xxx TODO
            pass



class ComponentAPI(BaseAPI):

    def __init__(self, config = "/etc/sfa/sfa_config.py", encoding = "utf-8", methods='sfa.methods',
                 peer_cert = None, interface = None, key_file = None, cert_file = None):

        BaseAPI.__init__(self, config=config, encoding=encoding, methods=methods, peer_cert=peer_cert,
                         interface=interface, key_file=key_file, cert_file=cert_file)
        self.encoding = encoding

        # Better just be documenting the API
        if config is None:
            return

        self.nodemanager = NodeManager(self.config)

    def sliver_exists(self):
        sliver_dict = self.nodemanager.GetXIDs()
        if slicename in sliver_dict.keys():
            return True
        else:
            return False

    def get_registry(self):
        addr, port = self.config.SFA_REGISTRY_HOST, self.config.SFA_REGISTRY_PORT
        url = "http://%(addr)s:%(port)s" % locals()
        server = xmlrpcprotocol.get_server(url, self.key_file, self.cert_file)
        return server

    def get_node_key(self):
        # this call requires no authentication,
        # so we can generate a random keypair here
        subject="component"
        (kfd, keyfile) = tempfile.mkstemp()
        (cfd, certfile) = tempfile.mkstemp()
        key = Keypair(create=True)
        key.save_to_file(keyfile)
        cert = Certificate(subject=subject)
        cert.set_issuer(key=key, subject=subject)
        cert.set_pubkey(key)
        cert.sign()
        cert.save_to_file(certfile)
        registry = self.get_registry()
        # the registry will scp the key onto the node
        registry.get_key()        

    def getCredential(self):
        """
        Get our credential from a remote registry
        """
        path = self.config.SFA_DATA_DIR
        config_dir = self.config.config_path
        cred_filename = path + os.sep + 'node.cred'
        try:
            credential = Credential(filename = cred_filename)
            return credential.save_to_string(save_parents=True)
        except IOError:
            node_pkey_file = config_dir + os.sep + "node.key"
            node_gid_file = config_dir + os.sep + "node.gid"
            cert_filename = path + os.sep + 'server.cert'
            if not os.path.exists(node_pkey_file) or \
               not os.path.exists(node_gid_file):
                self.get_node_key()

            # get node's hrn
            gid = GID(filename=node_gid_file)
            hrn = gid.get_hrn()
            # get credential from registry
            cert_str = Certificate(filename=cert_filename).save_to_string(save_parents=True)
            registry = self.get_registry()
            cred = registry.GetSelfCredential(cert_str, hrn, 'node')
            Credential(string=cred).save_to_file(credfile, save_parents=True)            

            return cred

    def clean_key_cred(self):
        """
        remove the existing keypair and cred  and generate new ones
        """
        files = ["server.key", "server.cert", "node.cred"]
        for f in files:
            filepath = KEYDIR + os.sep + f
            if os.path.isfile(filepath):
                os.unlink(f)

        # install the new key pair
        # GetCredential will take care of generating the new keypair
        # and credential
        self.get_node_key()
        self.getCredential()

    
