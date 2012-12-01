import datetime
#
from sfa.util.faults import MissingSfaInfo, UnknownSfaType, \
    RecordNotFound, SfaNotImplemented, SliverDoesNotExist, SearchFailed, \
    UnsupportedOperation 
from sfa.util.sfalogging import logger
from sfa.util.defaultdict import defaultdict
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.util.xrn import Xrn, hrn_to_urn, get_leaf
from sfa.util.cache import Cache

# one would think the driver should not need to mess with the SFA db, but..
from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, SliverAllocation

# used to be used in get_ticket
#from sfa.trust.sfaticket import SfaTicket
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

# the driver interface, mostly provides default behaviours
from sfa.managers.driver import Driver
from sfa.planetlab.plshell import PlShell
import sfa.planetlab.peers as peers
from sfa.planetlab.plaggregate import PlAggregate
from sfa.planetlab.plslices import PlSlices
from sfa.planetlab.plxrn import PlXrn, slicename_to_hrn, hostname_to_hrn, hrn_to_pl_slicename, xrn_to_hostname


def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
    return dict ( [ (rec[key],rec) for rec in recs ] )

#
# PlShell is just an xmlrpc serverproxy where methods
# can be sent as-is; it takes care of authentication
# from the global config
# 
class PlDriver (Driver):

    # the cache instance is a class member so it survives across incoming requests
    cache = None

    def __init__ (self, config):
        Driver.__init__ (self, config)
        self.shell = PlShell (config)
        self.cache=None
        if config.SFA_AGGREGATE_CACHING:
            if PlDriver.cache is None:
                PlDriver.cache = Cache()
            self.cache = PlDriver.cache
 
    ########################################
    ########## registry oriented
    ########################################

    def augment_records_with_testbed_info (self, sfa_records):
        return self.fill_record_info (sfa_records)

    ########## 
    def register (self, sfa_record, hrn, pub_key):
        type = sfa_record['type']
        pl_record = self.sfa_fields_to_pl_fields(type, hrn, sfa_record)

        if type == 'authority':
            sites = self.shell.GetSites([pl_record['login_base']])
            if not sites:
                # xxx when a site gets registered through SFA we need to set its max_slices
                if 'max_slices' not in pl_record:
                    pl_record['max_slices']=2
                pointer = self.shell.AddSite(pl_record)
            else:
                pointer = sites[0]['site_id']

        elif type == 'slice':
            acceptable_fields=['url', 'instantiation', 'name', 'description']
            for key in pl_record.keys():
                if key not in acceptable_fields:
                    pl_record.pop(key)
            slices = self.shell.GetSlices([pl_record['name']])
            if not slices:
                 pointer = self.shell.AddSlice(pl_record)
            else:
                 pointer = slices[0]['slice_id']

        elif type == 'user':
            persons = self.shell.GetPersons({'email':sfa_record['email']})
            if not persons:
                for key in ['first_name','last_name']:
                    if key not in sfa_record: sfa_record[key]='*from*sfa*'
                pointer = self.shell.AddPerson(dict(sfa_record))
            else:
                pointer = persons[0]['person_id']
    
            if 'enabled' in sfa_record and sfa_record['enabled']:
                self.shell.UpdatePerson(pointer, {'enabled': sfa_record['enabled']})
            # add this person to the site only if she is being added for the first
            # time by sfa and doesont already exist in plc
            if not persons or not persons[0]['site_ids']:
                login_base = get_leaf(sfa_record['authority'])
                self.shell.AddPersonToSite(pointer, login_base)
    
            # What roles should this user have?
            roles=[]
            if 'roles' in sfa_record: 
                # if specified in xml, but only low-level roles
                roles = [ role for role in sfa_record['roles'] if role in ['user','tech'] ]
            # at least user if no other cluse could be found
            if not roles:
                roles=['user']
            for role in roles:
                self.shell.AddRoleToPerson(role, pointer)
            # Add the user's key
            if pub_key:
                self.shell.AddPersonKey(pointer, {'key_type' : 'ssh', 'key' : pub_key})

        elif type == 'node':
            login_base = PlXrn(xrn=sfa_record['authority'],type='node').pl_login_base()
            nodes = self.shell.GetNodes([pl_record['hostname']])
            if not nodes:
                pointer = self.shell.AddNode(login_base, pl_record)
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
            self.shell.UpdateSite(pointer, new_sfa_record)
    
        elif type == "slice":
            pl_record=self.sfa_fields_to_pl_fields(type, hrn, new_sfa_record)
            if 'name' in pl_record:
                pl_record.pop('name')
                self.shell.UpdateSlice(pointer, pl_record)
    
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
            # when updating a user, we always get a 'email' field at this point
            # this is because 'email' is a native field in the RegUser object...
            if 'email' in update_fields and not update_fields['email']:
                del update_fields['email']
            self.shell.UpdatePerson(pointer, update_fields)
    
            if new_key:
                # must check this key against the previous one if it exists
                persons = self.shell.GetPersons([pointer], ['key_ids'])
                person = persons[0]
                keys = person['key_ids']
                keys = self.shell.GetKeys(person['key_ids'])
                
                # Delete all stale keys
                key_exists = False
                for key in keys:
                    if new_key != key['key']:
                        self.shell.DeleteKey(key['key_id'])
                    else:
                        key_exists = True
                if not key_exists:
                    self.shell.AddPersonKey(pointer, {'key_type': 'ssh', 'key': new_key})
    
        elif type == "node":
            self.shell.UpdateNode(pointer, new_sfa_record)

        return True
        

    ##########
    def remove (self, sfa_record):
        type=sfa_record['type']
        pointer=sfa_record['pointer']
        if type == 'user':
            persons = self.shell.GetPersons(pointer)
            # only delete this person if he has site ids. if he doesnt, it probably means
            # he was just removed from a site, not actually deleted
            if persons and persons[0]['site_ids']:
                self.shell.DeletePerson(pointer)
        elif type == 'slice':
            if self.shell.GetSlices(pointer):
                self.shell.DeleteSlice(pointer)
        elif type == 'node':
            if self.shell.GetNodes(pointer):
                self.shell.DeleteNode(pointer)
        elif type == 'authority':
            if self.shell.GetSites(pointer):
                self.shell.DeleteSite(pointer)

        return True





    ##
    # Convert SFA fields to PLC fields for use when registering or updating
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
                date = utcparse(sfa_record['expires'])
                expires = datetime_to_epoch(date)
                pl_record["expires"] = expires

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
            pl_record["login_base"] = PlXrn(xrn=hrn,type='authority').pl_login_base()
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
        self.fill_record_hrns(records)
        self.fill_record_sfa_info(records)
        return records

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
            node_list = self.shell.GetNodes(node_ids)
            nodes = list_to_dict(node_list, 'node_id')
        if site_ids:
            site_list = self.shell.GetSites(site_ids)
            sites = list_to_dict(site_list, 'site_id')
        if slice_ids:
            slice_list = self.shell.GetSlices(slice_ids)
            slices = list_to_dict(slice_list, 'slice_id')
        if person_ids:
            person_list = self.shell.GetPersons(person_ids)
            persons = list_to_dict(person_list, 'person_id')
            for person in persons:
                key_ids.extend(persons[person]['key_ids'])

        pl_records = {'node': nodes, 'authority': sites,
                      'slice': slices, 'user': persons}

        if key_ids:
            key_list = self.shell.GetKeys(key_ids)
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
            site_list = self.shell.GetSites(site_ids, ['site_id', 'login_base'])
            sites = list_to_dict(site_list, 'site_id')
        if person_ids:
            person_list = self.shell.GetPersons(person_ids, ['person_id', 'email'])
            persons = list_to_dict(person_list, 'person_id')
        if slice_ids:
            slice_list = self.shell.GetSlices(slice_ids, ['slice_id', 'name'])
            slices = list_to_dict(slice_list, 'slice_id')       
        if node_ids:
            node_list = self.shell.GetNodes(node_ids, ['node_id', 'hostname'])
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

            if 'expires' in record:
                date = utcparse(record['expires'])
                datestring = datetime_to_string(date)
                record['expires'] = datestring 
            
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
            pi_list = self.shell.GetPersons(pi_filter, ['person_id', 'site_ids'])
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
        
        # get the registry records
        person_list, persons = [], {}
        person_list = dbsession.query (RegRecord).filter(RegRecord.pointer.in_(person_ids))
        # create a hrns keyed on the sfa record's pointer.
        # Its possible for multiple records to have the same pointer so
        # the dict's value will be a list of hrns.
        persons = defaultdict(list)
        for person in person_list:
            persons[person.pointer].append(person)

        # get the pl records
        pl_person_list, pl_persons = [], {}
        pl_person_list = self.shell.GetPersons(person_ids, ['person_id', 'roles'])
        pl_persons = list_to_dict(pl_person_list, 'person_id')

        # fill sfa info
        for record in records:
            # skip records with no pl info (top level authorities)
            #if record['pointer'] == -1:
            #    continue 
            sfa_info = {}
            type = record['type']
            logger.info("fill_record_sfa_info - incoming record typed %s"%type)
            if (type == "slice"):
                # all slice users are researchers
                record['geni_urn'] = hrn_to_urn(record['hrn'], 'slice')
                record['PI'] = []
                record['researcher'] = []
                for person_id in record.get('person_ids', []):
                    hrns = [person.hrn for person in persons[person_id]]
                    record['researcher'].extend(hrns)                

                # pis at the slice's site
                if 'site_id' in record and record['site_id'] in site_pis:
                    pl_pis = site_pis[record['site_id']]
                    pi_ids = [pi['person_id'] for pi in pl_pis]
                    for person_id in pi_ids:
                        hrns = [person.hrn for person in persons[person_id]]
                        record['PI'].extend(hrns)
                        record['geni_creator'] = record['PI'] 
                
            elif (type.startswith("authority")):
                record['url'] = None
                logger.info("fill_record_sfa_info - authority xherex")
                if record['pointer'] != -1:
                    record['PI'] = []
                    record['operator'] = []
                    record['owner'] = []
                    for pointer in record.get('person_ids', []):
                        if pointer not in persons or pointer not in pl_persons:
                            # this means there is not sfa or pl record for this user
                            continue   
                        hrns = [person.hrn for person in persons[pointer]] 
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
                logger.info('setting user.email')
                sfa_info['email'] = record.get("email", "")
                sfa_info['geni_urn'] = hrn_to_urn(record['hrn'], 'user')
                sfa_info['geni_certificate'] = record['gid'] 
                # xxx TODO: PostalAddress, Phone
            record.update(sfa_info)


    ####################
    # plcapi works by changes, compute what needs to be added/deleted
    def update_relation (self, subject_type, target_type, relation_name, subject_id, target_ids):
        # hard-wire the code for slice/user for now, could be smarter if needed
        if subject_type =='slice' and target_type == 'user' and relation_name == 'researcher':
            subject=self.shell.GetSlices (subject_id)[0]
            current_target_ids = subject['person_ids']
            add_target_ids = list ( set (target_ids).difference(current_target_ids))
            del_target_ids = list ( set (current_target_ids).difference(target_ids))
            logger.debug ("subject_id = %s (type=%s)"%(subject_id,type(subject_id)))
            for target_id in add_target_ids:
                self.shell.AddPersonToSlice (target_id,subject_id)
                logger.debug ("add_target_id = %s (type=%s)"%(target_id,type(target_id)))
            for target_id in del_target_ids:
                logger.debug ("del_target_id = %s (type=%s)"%(target_id,type(target_id)))
                self.shell.DeletePersonFromSlice (target_id, subject_id)
        elif subject_type == 'authority' and target_type == 'user' and relation_name == 'pi':
            # due to the plcapi limitations this means essentially adding pi role to all people in the list
            # it's tricky to remove any pi role here, although it might be desirable
            persons = self.shell.GetPersons (target_ids)
            for person in persons: 
                if 'pi' not in person['roles']:
                    self.shell.AddRoleToPerson('pi',person['person_id'])
        else:
            logger.info('unexpected relation %s to maintain, %s -> %s'%(relation_name,subject_type,target_type))

        
    ########################################
    ########## aggregate oriented
    ########################################

    def testbed_name (self): return "myplc"

    def aggregate_version (self):
        return {}

    # first 2 args are None in case of resource discovery
    def list_resources (self, version=None, options={}):
        aggregate = PlAggregate(self)
        rspec =  aggregate.list_resources(version=version, options=options)
        return rspec

    def describe(self, urns, version, options={}, allocation_status=None):
        aggregate = PlAggregate(self)
        return aggregate.describe(urns, version=version, options=options)
    
    def status (self, urns, options={}):
        aggregate = PlAggregate(self)
        desc =  aggregate.describe(urns)
        return desc['geni_slivers']

    def allocate (self, urn, rspec_string, options={}):
        xrn = Xrn(urn)
        aggregate = PlAggregate(self)
        slices = PlSlices(self)
        peer = slices.get_peer(xrn.get_hrn())
        sfa_peer = slices.get_sfa_peer(xrn.get_hrn())
        slice_record=None    
        users = options.get('geni_users', [])
        if users:
            slice_record = users[0].get('slice_record', {})
    
        # parse rspec
        rspec = RSpec(rspec_string)
        requested_attributes = rspec.version.get_slice_attributes()
        
        # ensure site record exists
        site = slices.verify_site(xrn.hrn, slice_record, peer, sfa_peer, options=options)
        # ensure slice record exists
        slice = slices.verify_slice(xrn.hrn, slice_record, peer, sfa_peer, options=options)
        # ensure person records exists
        persons = slices.verify_persons(xrn.hrn, slice, users, peer, sfa_peer, options=options)
        # ensure slice attributes exists
        slices.verify_slice_attributes(slice, requested_attributes, options=options)
        
        # add/remove slice from nodes
        requested_slivers = []
        for node in rspec.version.get_nodes_with_slivers():
            hostname = None
            if node.get('component_name'):
                hostname = node.get('component_name').strip()
            elif node.get('component_id'):
                hostname = xrn_to_hostname(node.get('component_id').strip())
            if hostname:
                requested_slivers.append(hostname)
        nodes = slices.verify_slice_nodes(slice, requested_slivers, peer)

        # update all sliver allocation states setting then to geni_allocated   
        sliver_ids = []
        for node in nodes:
            sliver_hrn = '%s.%s-%s' % (self.hrn, slice['slice_id'], node['node_id'])
            sliver_id = Xrn(sliver_hrn, type='sliver').urn
            sliver_ids.append(sliver_id)
        SliverAllocation.set_allocations(sliver_ids, 'geni_allocated')
         
        # add/remove links links 
        slices.verify_slice_links(slice, rspec.version.get_link_requests(), nodes)

        # add/remove leases
        requested_leases = []
        kept_leases = []
        for lease in rspec.version.get_leases():
            requested_lease = {}
            if not lease.get('lease_id'):
               requested_lease['hostname'] = xrn_to_hostname(lease.get('component_id').strip())
               requested_lease['start_time'] = lease.get('start_time')
               requested_lease['duration'] = lease.get('duration')
            else:
               kept_leases.append(int(lease['lease_id']))
            if requested_lease.get('hostname'):
                requested_leases.append(requested_lease)

        leases = slices.verify_slice_leases(slice, requested_leases, kept_leases, peer)
        # handle MyPLC peer association.
        # only used by plc and ple.
        slices.handle_peer(site, slice, persons, peer)
        
        return aggregate.describe([xrn.get_urn()], version=rspec.version)

    def provision(self, urns, options={}):
        # update sliver allocation states and set them to geni_provisioned
        aggregate = PlAggregate(self)
        slivers = aggregate.get_slivers(urns)
        sliver_ids = [sliver['sliver_id'] for sliver in slivers]
        SliverAllocation.set_allocations(sliver_ids, 'geni_provisioned')
     
        return self.describe(urns, None, options=options)

    def delete(self, urns, options={}):
        # collect sliver ids so we can update sliver allocation states after
        # we remove the slivers.
        aggregate = PlAggregate(self)
        slivers = aggregate.get_slivers(urns)
        slice_id = slivers[0]['slice_id'] 
        node_ids = []
        sliver_ids = []
        for sliver in slivers:
            node_ids.append(sliver['node_id'])
            sliver_ids.append(sliver['sliver_id']) 

        # determine if this is a peer slice
        # xxx I wonder if this would not need to use PlSlices.get_peer instead 
        # in which case plc.peers could be deprecated as this here
        # is the only/last call to this last method in plc.peers
        slice_hrn = PlXrn(auth=self.hrn, slicename=slivers[0]['name']).get_hrn()     
        peer = peers.get_peer(self, slice_hrn)
        try:
            if peer:
                self.shell.UnBindObjectFromPeer('slice', slice_id, peer)
 
            self.shell.DeleteSliceFromNodes(slice_id, node_ids)
 
            # delete sliver allocation states
            SliverAllocation.delete_allocations(sliver_ids)
        finally:
            if peer:
                self.shell.BindObjectToPeer('slice', slice_id, peer, slice['peer_slice_id'])

        # prepare return struct
        geni_slivers = []
        for node_id in node_ids:
            sliver_hrn = '%s.%s-%s' % (self.hrn, slice_id, node_id)
            geni_slivers.append(
                {'geni_sliver_urn': Xrn(sliver_hrn, type='sliver').urn,
                 'geni_allocation_status': 'geni_unallocated',
                 'geni_expires': datetime_to_string(utcparse(slivers[0]['expires']))})  
        return geni_slivers
    
    def renew (self, urns, expiration_time, options={}):
        # we can only renew slices, not individual slivers. ignore sliver
        # ids in the urn 
        names = []
        for urn in urns:
            xrn = PlXrn(xrn=urn, type='slice')
            names.append(xrn.pl_slicename())
        slices = self.shell.GetSlices(names, ['slice_id'])
        if not slices:
            raise SearchFailed(urns)
        slice = slices[0]
        requested_time = utcparse(expiration_time)
        record = {'expires': int(datetime_to_epoch(requested_time))}
        try:
            self.shell.UpdateSlice(slice['slice_id'], record)
            return True
        except:
            return False

    def perform_operational_action (self, urns, action, options={}):
        # MyPLC doesn't support operational actions. Lets pretend like it
        # supports start, but reject everything else.
        action = action.lower()
        if action == 'geni_start':
            pass
        else:
            raise UnsupportedOperation(action)
        description = self.describe(urns, None, options)
        return description['geni_slivers']

    # set the 'enabled' tag to 0
    def shutdown (self, xrn, options={}):
        xrn = PlXrn(xrn=xrn, type='slice')
        slicename = xrn.pl_slicename()
        slices = self.shell.GetSlices({'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice_id = slices[0]['slice_id']
        slice_tags = self.shell.GetSliceTags({'slice_id': slice_id, 'tagname': 'enabled'})
        if not slice_tags:
            self.shell.AddSliceTag(slice_id, 'enabled', '0')
        elif slice_tags[0]['value'] != "0":
            tag_id = slice_tags[0]['slice_tag_id']
            self.shell.UpdateSliceTag(tag_id, '0')
        return 1
