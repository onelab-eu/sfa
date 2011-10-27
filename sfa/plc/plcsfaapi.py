import xmlrpclib
#
from sfa.util.faults import MissingSfaInfo
from sfa.util.sfalogging import logger
from sfa.util.table import SfaTable

from sfa.util.xrn import hrn_to_urn
from sfa.util.plxrn import slicename_to_hrn, hostname_to_hrn, hrn_to_pl_slicename, hrn_to_pl_login_base

from sfa.server.sfaapi import SfaApi

#################### xxx should move into util/defaultdict
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
    keys = [rec[key] for rec in recs]
    return dict(zip(keys, recs))

class PlcSfaApi(SfaApi):

    def __init__ (self, encoding="utf-8", methods='sfa.methods', 
                  config = "/etc/sfa/sfa_config.py", 
                  peer_cert = None, interface = None, 
                  key_file = None, cert_file = None, cache = None):
        SfaApi.__init__(self, encoding=encoding, methods=methods, 
                        config=config, 
                        peer_cert=peer_cert, interface=interface, 
                        key_file=key_file, 
                        cert_file=cert_file, cache=cache)
 
        self.SfaTable = SfaTable
        # Initialize the PLC shell only if SFA wraps a myPLC
        rspec_type = self.config.get_aggregate_type()
        if (rspec_type == 'pl' or rspec_type == 'vini' or \
            rspec_type == 'eucalyptus' or rspec_type == 'max'):
            self.plshell = self.getPLCShell()
            self.plshell_version = "4.3"

    def getPLCShell(self):
        self.plauth = {'Username': self.config.SFA_PLC_USER,
                       'AuthMethod': 'password',
                       'AuthString': self.config.SFA_PLC_PASSWORD}

        # The native shell (PLC.Shell.Shell) is more efficient than xmlrpc,
        # but it leaves idle db connections open. use xmlrpc until we can figure
        # out why PLC.Shell.Shell doesn't close db connection properly     
        #try:
        #    sys.path.append(os.path.dirname(os.path.realpath("/usr/bin/plcsh")))
        #    self.plshell_type = 'direct'
        #    import PLC.Shell
        #    shell = PLC.Shell.Shell(globals = globals())
        #except:
        
        self.plshell_type = 'xmlrpc' 
        url = self.config.SFA_PLC_URL
        shell = xmlrpclib.Server(url, verbose = 0, allow_none = True)
        return shell

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
        node_ids, site_ids, slice_ids = [], [], [] 
        person_ids, key_ids = [], []
        type_map = {'node': node_ids, 'authority': site_ids,
                    'slice': slice_ids, 'user': person_ids}
                  
        for record in records:
            for type in type_map:
                if type == record['type']:
                    type_map[type].append(record['pointer'])

        # get pl records
        nodes, sites, slices, persons, keys = {}, {}, {}, {}, {}
        if node_ids:
            node_list = self.plshell.GetNodes(self.plauth, node_ids)
            nodes = list_to_dict(node_list, 'node_id')
        if site_ids:
            site_list = self.plshell.GetSites(self.plauth, site_ids)
            sites = list_to_dict(site_list, 'site_id')
        if slice_ids:
            slice_list = self.plshell.GetSlices(self.plauth, slice_ids)
            slices = list_to_dict(slice_list, 'slice_id')
        if person_ids:
            person_list = self.plshell.GetPersons(self.plauth, person_ids)
            persons = list_to_dict(person_list, 'person_id')
            for person in persons:
                key_ids.extend(persons[person]['key_ids'])

        pl_records = {'node': nodes, 'authority': sites,
                      'slice': slices, 'user': persons}

        if key_ids:
            key_list = self.plshell.GetKeys(self.plauth, key_ids)
            keys = list_to_dict(key_list, 'key_id')

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
                    logger.info("user record has no 'key_ids' - need to import from myplc ?")
                else:
                    pubkeys = [keys[key_id]['key'] for key_id in record['key_ids'] if key_id in keys] 
                    record['keys'] = pubkeys

        # fill in record hrns
        records = self.fill_record_hrns(records)   
 
        return records

    def fill_record_hrns(self, records):
        """
        convert pl ids to hrns
        """

        # get ids
        slice_ids, person_ids, site_ids, node_ids = [], [], [], []
        for record in records:
            if 'site_id' in record:
                site_ids.append(record['site_id'])
            if 'site_ids' in record:
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
            site_list = self.plshell.GetSites(self.plauth, site_ids, ['site_id', 'login_base'])
            sites = list_to_dict(site_list, 'site_id')
        if person_ids:
            person_list = self.plshell.GetPersons(self.plauth, person_ids, ['person_id', 'email'])
            persons = list_to_dict(person_list, 'person_id')
        if slice_ids:
            slice_list = self.plshell.GetSlices(self.plauth, slice_ids, ['slice_id', 'name'])
            slices = list_to_dict(slice_list, 'slice_id')       
        if node_ids:
            node_list = self.plshell.GetNodes(self.plauth, node_ids, ['node_id', 'hostname'])
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

            if 'site_id' in record:
                site = sites[record['site_id']]
                login_base = site['login_base']
                record['site'] = ".".join([auth_hrn, login_base])
            if 'person_ids' in record:
                emails = [persons[person_id]['email'] for person_id in record['person_ids'] \
                          if person_id in  persons]
                usernames = [email.split('@')[0] for email in emails]
                person_hrns = [".".join([auth_hrn, login_base, username]) for username in usernames]
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
            
        return records   

    def fill_record_sfa_info(self, records):

        def startswith(prefix, values):
            return [value for value in values if value.startswith(prefix)]

        # get person ids
        person_ids = []
        site_ids = []
        for record in records:
            person_ids.extend(record.get("person_ids", []))
            site_ids.extend(record.get("site_ids", [])) 
            if 'site_id' in record:
                site_ids.append(record['site_id']) 
        
        # get all pis from the sites we've encountered
        # and store them in a dictionary keyed on site_id 
        site_pis = {}
        if site_ids:
            pi_filter = {'|roles': ['pi'], '|site_ids': site_ids} 
            pi_list = self.plshell.GetPersons(self.plauth, pi_filter, ['person_id', 'site_ids'])
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
        pl_person_list = self.plshell.GetPersons(self.plauth, person_ids, ['person_id', 'roles'])
        pl_persons = list_to_dict(pl_person_list, 'person_id')

        # fill sfa info
        for record in records:
            # skip records with no pl info (top level authorities)
            #if record['pointer'] == -1:
            #    continue 
            sfa_info = {}
            type = record['type']
            if (type == "slice"):
                # all slice users are researchers
                record['geni_urn'] = hrn_to_urn(record['hrn'], 'slice')
                record['PI'] = []
                record['researcher'] = []
                for person_id in record.get('person_ids', []):
                    hrns = [person['hrn'] for person in persons[person_id]]
                    record['researcher'].extend(hrns)                

                # pis at the slice's site
                if 'site_id' in record and record['site_id'] in site_pis:
                    pl_pis = site_pis[record['site_id']]
                    pi_ids = [pi['person_id'] for pi in pl_pis]
                    for person_id in pi_ids:
                        hrns = [person['hrn'] for person in persons[person_id]]
                        record['PI'].extend(hrns)
                        record['geni_creator'] = record['PI'] 
                
            elif (type.startswith("authority")):
                record['url'] = None
                if record['hrn'] in self.aggregates:
                    
                    record['url'] = self.aggregates[record['hrn']].get_url()

                if record['pointer'] != -1:
                    record['PI'] = []
                    record['operator'] = []
                    record['owner'] = []
                    for pointer in record.get('person_ids', []):
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
            record.update(sfa_info)

    def fill_record_info(self, records):
        """
        Given a SFA record, fill in the PLC specific and SFA specific
        fields in the record. 
        """
        if not isinstance(records, list):
            records = [records]

        self.fill_record_pl_info(records)
        self.fill_record_sfa_info(records)

    def update_membership_list(self, oldRecord, record, listName, addFunc, delFunc):
        # get a list of the HRNs that are members of the old and new records
        if oldRecord:
            oldList = oldRecord.get(listName, [])
        else:
            oldList = []     
        newList = record.get(listName, [])
        # xxx ugly hack - somehow we receive here a list of {'text':value} 
        # instead of an expected list of strings
        # please remove once this is issue is cleanly fixed
        def normalize (value):
            from types import StringTypes
            if isinstance(value,StringTypes): return value
            elif isinstance(value,dict): 
                newvalue=value['text']
                logger.info("Normalizing %s=>%s"%(value,newvalue))
                return newvalue
        newList=[normalize(v) for v in newList]

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
                                        self.plshell.AddPersonToSlice,
                                        self.plshell.DeletePersonFromSlice)
        elif record.type == "authority":
            # xxx TODO
            pass
