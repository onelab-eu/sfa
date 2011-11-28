#
from sfa.util.faults import MissingSfaInfo, UnknownSfaType
from sfa.util.sfalogging import logger
from sfa.util.table import SfaTable
from sfa.util.defaultdict import defaultdict

from sfa.util.xrn import hrn_to_urn, get_leaf
from sfa.util.plxrn import slicename_to_hrn, hostname_to_hrn, hrn_to_pl_slicename, hrn_to_pl_login_base

# the driver interface, mostly provides default behaviours
from sfa.managers.driver import Driver

from sfa.plc.plshell import PlShell

def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
    keys = [rec[key] for rec in recs]
    return dict(zip(keys, recs))

#
# inheriting Driver is not very helpful in the PL case but
# makes sense in the general case
# 
# PlShell is just an xmlrpc serverproxy where methods
# can be sent as-is; it takes care of authentication
# from the global config
# 
# so OTOH we inherit PlShell just so one can do driver.GetNodes
# which would not make much sense in the context of other testbeds
# so ultimately PlDriver might just as well drop the PlShell inheritance
# 
class PlDriver (Driver, PlShell):

    def __init__ (self, config):
        PlShell.__init__ (self, config)
 
        self.hrn = config.SFA_INTERFACE_HRN
        # xxx thgen fixme - use SfaTable hardwired for now 
        # will need to extend generic to support multiple storage systems
        #self.SfaTable = SfaTable
        # Initialize the PLC shell only if SFA wraps a myPLC
        rspec_type = config.get_aggregate_type()
        assert (rspec_type == 'pl' or rspec_type == 'vini' or \
                    rspec_type == 'eucalyptus' or rspec_type == 'max')

    ########## disabled users 
    def is_enabled_entity (self, record):
        self.fill_record_info(record)
        if record['type'] == 'user':
            return record['enabled']
        # only users can be disabled
        return True

    ########## 
    def register (self, sfa_record, hrn, pub_key):
        type = sfa_record['type']
        pl_record = self.sfa_fields_to_pl_fields(type, hrn, sfa_record)

        if type == 'authority':
            sites = self.GetSites([pl_record['login_base']])
            if not sites:
                pointer = self.AddSite(pl_record)
            else:
                pointer = sites[0]['site_id']

        elif type == 'slice':
            acceptable_fields=['url', 'instantiation', 'name', 'description']
            for key in pl_record.keys():
                if key not in acceptable_fields:
                    pl_record.pop(key)
            slices = self.GetSlices([pl_record['name']])
            if not slices:
                 pointer = self.AddSlice(pl_record)
            else:
                 pointer = slices[0]['slice_id']

        elif type == 'user':
            persons = self.GetPersons([sfa_record['email']])
            if not persons:
                pointer = self.AddPerson(dict(sfa_record))
            else:
                pointer = persons[0]['person_id']
    
            if 'enabled' in sfa_record and sfa_record['enabled']:
                self.UpdatePerson(pointer, {'enabled': sfa_record['enabled']})
            # add this person to the site only if she is being added for the first
            # time by sfa and doesont already exist in plc
            if not persons or not persons[0]['site_ids']:
                login_base = get_leaf(sfa_record['authority'])
                self.AddPersonToSite(pointer, login_base)
    
            # What roles should this user have?
            self.AddRoleToPerson('user', pointer)
            # Add the user's key
            if pub_key:
                self.AddPersonKey(pointer, {'key_type' : 'ssh', 'key' : pub_key})

        elif type == 'node':
            login_base = hrn_to_pl_login_base(sfa_record['authority'])
            nodes = api.driver.GetNodes([pl_record['hostname']])
            if not nodes:
                pointer = api.driver.AddNode(login_base, pl_record)
            else:
                pointer = nodes[0]['node_id']
    
        return pointer
        
    ##########
    # xxx actually old_sfa_record comes filled with plc stuff as well in the original code
    def update (self, old_sfa_record, new_sfa_record, hrn, new_key):
        pointer = old_sfa_record['pointer']
        type = old_sfa_record['type']

        # new_key implemented for users only
        if new_key and type not in [ 'user' ]:
            raise UnknownSfaType(type)

        if (type == "authority"):
            self.UpdateSite(pointer, new_sfa_record)
    
        elif type == "slice":
            pl_record=self.sfa_fields_to_pl_fields(type, hrn, new_sfa_record)
            if 'name' in pl_record:
                pl_record.pop('name')
                self.UpdateSlice(pointer, pl_record)
    
        elif type == "user":
            # SMBAKER: UpdatePerson only allows a limited set of fields to be
            #    updated. Ideally we should have a more generic way of doing
            #    this. I copied the field names from UpdatePerson.py...
            update_fields = {}
            all_fields = new_sfa_record
            for key in all_fields.keys():
                if key in ['first_name', 'last_name', 'title', 'email',
                           'password', 'phone', 'url', 'bio', 'accepted_aup',
                           'enabled']:
                    update_fields[key] = all_fields[key]
            self.UpdatePerson(pointer, update_fields)
    
            if new_key:
                # must check this key against the previous one if it exists
                persons = self.GetPersons([pointer], ['key_ids'])
                person = persons[0]
                keys = person['key_ids']
                keys = self.GetKeys(person['key_ids'])
                
                # Delete all stale keys
                key_exists = False
                for key in keys:
                    if new_key != key['key']:
                        self.DeleteKey(key['key_id'])
                    else:
                        key_exists = True
                if not key_exists:
                    self.AddPersonKey(pointer, {'key_type': 'ssh', 'key': new_key})
    
        elif type == "node":
            self.UpdateNode(pointer, new_sfa_record)

        return True
        

    ##########
    def remove (self, sfa_record):
        type=sfa_record['type']
        pointer=sfa_record['pointer']
        if type == 'user':
            persons = self.GetPersons(pointer)
            # only delete this person if he has site ids. if he doesnt, it probably means
            # he was just removed from a site, not actually deleted
            if persons and persons[0]['site_ids']:
                self.DeletePerson(pointer)
        elif type == 'slice':
            if self.GetSlices(pointer):
                self.DeleteSlice(pointer)
        elif type == 'node':
            if self.GetNodes(pointer):
                self.DeleteNode(pointer)
        elif type == 'authority':
            if self.GetSites(pointer):
                self.DeleteSite(pointer)

        return True





    ##
    # Convert SFA fields to PLC fields for use when registering up updating
    # registry record in the PLC database
    #

    def sfa_fields_to_pl_fields(self, type, hrn, sfa_record):

        pl_record = {}
 
        if type == "slice":
            pl_record["name"] = hrn_to_pl_slicename(hrn)
            if "instantiation" in sfa_record:
                pl_record['instantiation']=sfa_record['instantiation']
            else:
                pl_record["instantiation"] = "plc-instantiated"
	    if "url" in sfa_record:
               pl_record["url"] = sfa_record["url"]
	    if "description" in sfa_record:
	        pl_record["description"] = sfa_record["description"]
	    if "expires" in sfa_record:
	        pl_record["expires"] = int(sfa_record["expires"])

        elif type == "node":
            if not "hostname" in pl_record:
                # fetch from sfa_record
                if "hostname" not in sfa_record:
                    raise MissingSfaInfo("hostname")
                pl_record["hostname"] = sfa_record["hostname"]
            if "model" in sfa_record: 
                pl_record["model"] = sfa_record["model"]
            else:
                pl_record["model"] = "geni"

        elif type == "authority":
            pl_record["login_base"] = hrn_to_pl_login_base(hrn)
            if "name" not in sfa_record:
                pl_record["name"] = hrn
            if "abbreviated_name" not in sfa_record:
                pl_record["abbreviated_name"] = hrn
            if "enabled" not in sfa_record:
                pl_record["enabled"] = True
            if "is_public" not in sfa_record:
                pl_record["is_public"] = True

        return pl_record

    ####################
    def fill_record_info(self, records):
        """
        Given a (list of) SFA record, fill in the PLC specific 
        and SFA specific fields in the record. 
        """
        if not isinstance(records, list):
            records = [records]

        self.fill_record_pl_info(records)
        self.fill_record_sfa_info(records)

    def fill_record_pl_info(self, records):
        """
        Fill in the planetlab specific fields of a SFA record. This
        involves calling the appropriate PLC method to retrieve the 
        database record for the object.
            
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
            node_list = self.GetNodes(node_ids)
            nodes = list_to_dict(node_list, 'node_id')
        if site_ids:
            site_list = self.GetSites(site_ids)
            sites = list_to_dict(site_list, 'site_id')
        if slice_ids:
            slice_list = self.GetSlices(slice_ids)
            slices = list_to_dict(slice_list, 'slice_id')
        if person_ids:
            person_list = self.GetPersons(person_ids)
            persons = list_to_dict(person_list, 'person_id')
            for person in persons:
                key_ids.extend(persons[person]['key_ids'])

        pl_records = {'node': nodes, 'authority': sites,
                      'slice': slices, 'user': persons}

        if key_ids:
            key_list = self.GetKeys(key_ids)
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
            site_list = self.GetSites(site_ids, ['site_id', 'login_base'])
            sites = list_to_dict(site_list, 'site_id')
        if person_ids:
            person_list = self.GetPersons(person_ids, ['person_id', 'email'])
            persons = list_to_dict(person_list, 'person_id')
        if slice_ids:
            slice_list = self.GetSlices(slice_ids, ['slice_id', 'name'])
            slices = list_to_dict(slice_list, 'slice_id')       
        if node_ids:
            node_list = self.GetNodes(node_ids, ['node_id', 'hostname'])
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

    # aggregates is basically api.aggregates
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
            pi_list = self.GetPersons(pi_filter, ['person_id', 'site_ids'])
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
        # xxx thgen fixme - use SfaTable hardwired for now 
        # table = self.SfaTable()
        table = SfaTable()
        person_list, persons = [], {}
        person_list = table.find({'type': 'user', 'pointer': person_ids})
        # create a hrns keyed on the sfa record's pointer.
        # Its possible for multiple records to have the same pointer so
        # the dict's value will be a list of hrns.
        persons = defaultdict(list)
        for person in person_list:
            persons[person['pointer']].append(person)

        # get the pl records
        pl_person_list, pl_persons = [], {}
        pl_person_list = self.GetPersons(person_ids, ['person_id', 'roles'])
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

    ####################
    def update_membership(self, oldRecord, record):
        if record.type == "slice":
            self.update_membership_list(oldRecord, record, 'researcher',
                                        self.AddPersonToSlice,
                                        self.DeletePersonFromSlice)
        elif record.type == "authority":
            logger.info("update_membership 'autority' not implemented")
            pass
        else:
            pass

    def update_membership_list(self, oldRecord, record, listName, addFunc, delFunc):
        # get a list of the HRNs that are members of the old and new records
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
        # xxx thgen fixme - use SfaTable hardwired for now 
        #table = self.SfaTable()
        table = SfaTable()
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
                addFunc(personId, containerId)

        # remove people who are in the old list, but not the new list
        for personId in oldIdList:
            if not (personId in newIdList):
                delFunc(personId, containerId)
