##
# Implements support for SFA records
#
# TODO: Use existing PLC database methods? or keep this separate?
##

from types import StringTypes
from sfa.trust.gid import GID
from sfa.storage.parameter import Parameter
from sfa.util.xrn import get_authority
from sfa.storage.row import Row
from sfa.util.xml import XML 
from sfa.util.sfalogging import logger

class SfaRecord(Row):
    """ 
    The SfaRecord class implements an SFA Record. A SfaRecord is a tuple
    (Hrn, GID, Type, Info).
 
    Hrn specifies the Human Readable Name of the object
    GID is the GID of the object
    Type is user | authority | slice | component
 
    Info is comprised of the following sub-fields
           pointer = a pointer to the record in the PL database
 
    The pointer is interpreted depending on the type of the record. For example,
    if the type=="user", then pointer is assumed to be a person_id that indexes
    into the persons table.
 
    A given HRN may have more than one record, provided that the records are
    of different types.
    """

    table_name = 'sfa'
    
    primary_key = 'record_id'

    ### the wsdl generator assumes this is named 'fields'
    internal_fields = {
        'record_id': Parameter(int, 'An id that uniquely identifies this record', ro=True),
        'pointer': Parameter(int, 'An id that uniquely identifies this record in an external database ')
    }

    fields = {
        'authority': Parameter(str, "The authority for this record"),
        'peer_authority': Parameter(str, "The peer authority for this record"),
        'hrn': Parameter(str, "Human readable name of object"),
        'gid': Parameter(str, "GID of the object"),
        'type': Parameter(str, "Record type"),
        'last_updated': Parameter(int, 'Date and time of last update', ro=True),
        'date_created': Parameter(int, 'Date and time this record was created', ro=True),
    }
    all_fields = dict(fields.items() + internal_fields.items())
    ##
    # Create an SFA Record
    #
    # @param name if !=None, assign the name of the record
    # @param gid if !=None, assign the gid of the record
    # @param type one of user | authority | slice | component
    # @param pointer is a pointer to a PLC record
    # @param dict if !=None, then fill in this record from the dictionary

    def __init__(self, hrn=None, gid=None, type=None, pointer=None, authority=None, peer_authority=None, dict=None, string=None):
        self.dirty = True
        self.hrn = None
        self.gid = None
        self.type = None
        self.pointer = None
        self.set_peer_auth(peer_authority)
        self.set_authority(authority)
        if hrn:
            self.set_name(hrn)
        if gid:
            self.set_gid(gid)
        if type:
            self.set_type(type)
        if pointer:
            self.set_pointer(pointer)
        if dict:
            self.load_from_dict(dict)
        if string:
            self.load_from_string(string)


    def validate_last_updated(self, last_updated):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        
    def update(self, new_dict):
        if isinstance(new_dict, list):
            new_dict = new_dict[0]

        # Convert any boolean strings to real bools
        for key in new_dict:
            if isinstance(new_dict[key], StringTypes):
                if new_dict[key].lower() in ["true"]:
                    new_dict[key] = True
                elif new_dict[key].lower() in ["false"]:
                    new_dict[key] = False
        dict.update(self, new_dict)

    ##
    # Set the name of the record
    #
    # @param hrn is a string containing the HRN

    def set_name(self, hrn):
        """
        Set the name of the record
        """
        self.hrn = hrn
        self['hrn'] = hrn
        self.dirty = True

    def set_authority(self, authority):
        """
        Set the authority
        """
        if not authority:
            authority = ""
        self.authority = authority
        self['authority'] = authority
        self.dirty = True    
        

    ##
    # Set the GID of the record
    #
    # @param gid is a GID object or the string representation of a GID object

    def set_gid(self, gid):
        """
        Set the GID of the record
        """

        if isinstance(gid, StringTypes):
            self.gid = gid
            self['gid'] = gid
        else:
            self.gid = gid.save_to_string(save_parents=True)
            self['gid'] = gid.save_to_string(save_parents=True)
        self.dirty = True

    ##
    # Set the type of the record
    #
    # @param type is a string: user | authority | slice | component

    def set_type(self, type):
        """
        Set the type of the record
        """
        self.type = type
        self['type'] = type
        self.dirty = True

    ##
    # Set the pointer of the record
    #
    # @param pointer is an integer containing the ID of a PLC record

    def set_pointer(self, pointer):
        """
        Set the pointer of the record
        """
        self.pointer = pointer
        self['pointer'] = pointer
        self.dirty = True


    def set_peer_auth(self, peer_authority):
        self.peer_authority = peer_authority
        self['peer_authority'] = peer_authority
        self.dirty = True

    ##
    # Return the name (HRN) of the record

    def get_name(self):
        """
        Return the name (HRN) of the record
        """
        return self.hrn

    ##
    # Return the type of the record

    def get_type(self):
        """
        Return the type of the record
        """
        return self.type

    ##
    # Return the pointer of the record. The pointer is an integer that may be
    # used to look up the record in the PLC database. The evaluation of pointer
    # depends on the type of the record

    def get_pointer(self):
        """
        Return the pointer of the record. The pointer is an integer that may be
        used to look up the record in the PLC database. The evaluation of pointer
        depends on the type of the record
        """
        return self.pointer

    ##
    # Return the GID of the record, in the form of a GID object
    # TODO: not the best name for the function, because we have things called
    # gidObjects in the Cred

    def get_gid_object(self):
        """
        Return the GID of the record, in the form of a GID object
        """
        return GID(string=self.gid)

    ##
    # Returns the value of a field

    def get_field(self, fieldname, default=None):
        # sometimes records act like classes, and sometimes they act like dicts
        try:
            return getattr(self, fieldname)
        except AttributeError:
            try:
                 return self[fieldname]
            except KeyError:
                 if default != None:
                     return default
                 else:
                     raise

    ##
    # Returns a list of field names in this record. 

    def get_field_names(self):
        """
        Returns a list of field names in this record.
        """
        return self.fields.keys()

    ##
    # Given a field name ("hrn", "gid", ...) return the value of that field.
    #
    # @param fieldname is the name of field to be returned

    def get_field_value_string(self, fieldname):
        """
        Given a field name ("hrn", "gid", ...) return the value of that field.
        """
        if fieldname == "authority":
            val = get_authority(self['hrn'])
        else:
            try:
                val = getattr(self, fieldname)
            except:
                val = self[fieldname] 
        if isinstance(val, str):
            return "'" + str(val) + "'"
        else:
            return str(val)

    ##
    # Given a list of field names, return a list of values for those public.
    #
    # @param fieldnames is a list of field names

    def get_field_value_strings(self, fieldnames):
        """
        Given a list of field names, return a list of values for those public.
        """
        return [ self.get_field_value_string (fieldname) for fieldname in fieldnames ]

    ##
    # Return the record in the form of a dictionary

    def as_dict(self):
        """
        Return the record in the form of a dictionary
        """
        return dict(self)

    ##
    # Load the record from a dictionary
    #
    # @param dict dictionary to load record public from

    def load_from_dict(self, dict):
        """
        Load the record from a dictionary 
        """

        self.set_name(dict['hrn'])
        gidstr = dict.get("gid", None)
        if gidstr:
            self.set_gid(dict['gid'])

        if "pointer" in dict:
           self.set_pointer(dict['pointer'])

        self.set_type(dict['type'])
        self.update(dict)        
    
    ##
    # Save the record to a string. The string contains an XML representation of
    # the record.

    def save_to_string(self):
        """
        Save the record to a string. The string contains an XML representation of
        the record.
        """
        recorddict = self.as_dict()
        filteredDict = dict([(key, val) for (key, val) in recorddict.iteritems() if key in self.fields.keys()])
        record = XML('<record/>')
        record.parse_dict(filteredDict)
        str = record.toxml()
        return str

    ##
    # Load the record from a string. The string is assumed to contain an XML
    # representation of the record.

    def load_from_string(self, str):
        """
        Load the record from a string. The string is assumed to contain an XML
        representation of the record.
        """
        #dict = xmlrpclib.loads(str)[0][0]

        record = XML(str)
        self.load_from_dict(record.todict())

    ##
    # Dump the record to stdout
    #
    # @param dump_parents if true, then the parents of the GID will be dumped

    def dump(self, dump_parents=False):
        """
        Walk tree and dump records.
        """
        #print "RECORD", self.name
        #print "        hrn:", self.name
        #print "       type:", self.type
        #print "        gid:"
        #if (not self.gid):
        #    print "        None"
        #else:
        #    self.get_gid_object().dump(8, dump_parents)
        #print "    pointer:", self.pointer
       
        order = SfaRecord.fields.keys() 
        for key in self.keys():
            if key not in order:
                order.append(key)
        for key in order:
            if key in self and key in self.fields:
                if key in 'gid' and self[key]:
                    gid = GID(string=self[key])
                    print "     %s:" % key
                    gid.dump(8, dump_parents)
                else:    
                    print "     %s: %s" % (key, self[key])
    
    def summary_string(self):
        return "Record(record_id=%s, hrn=%s, type=%s, auth=%s, pointer=%s)" % \
                (self.get('record_id'), self.get('hrn'), self.get('type'), self.get('auth'), \
                 self.get('pointer'))

    def getdict(self):
        return dict(self)
   
    def sync(self, verbose=False):
        """ 
        Sync this record with the database.
        """ 
        from sfa.storage.table import SfaTable
        table = SfaTable()
        filter = {}
        if self.get('record_id'):
            filter['record_id'] = self.get('record_id')
        if self.get('hrn') and self.get('type'):
            filter['hrn'] = self.get('hrn') 
            filter['type'] = self.get('type')
            if self.get('pointer'):
                filter['pointer'] = self.get('pointer')
        existing_records = table.find(filter)
        if not existing_records:
            table.insert(self)
            if verbose:
                logger.info("Inserted record: %s" %self.summary_string()) 
        else:
            existing_record = existing_records[0]
            self['record_id'] = existing_record['record_id']
            table.upate(self) 
            if verbose:
                logger.info("Updated record: %s" % self.summary_string()) 

    def delete(self, verbose=False):
        """
        Remove record from the database.
        """
        from sfa.storage.table import SfaTable
        table = SfaTable()
        if self.get('record_id'):
            filter['record_id'] = self.get('record_id')
        if self.get('hrn') and self.get('type'):
            filter['hrn'] = self.get('hrn')
            filter['type'] = self.get('type')
            if self.get('pointer'):
                filter['pointer'] = self.get('pointer')
        existing_records = table.find(filter)
        for record in existing_records:
            table.remove(record)
            if verbose:
                logger.info("Removed record: %s" % self.summary_string())    

class UserRecord(SfaRecord):

    fields = {
        'email': Parameter(str, 'email'),
        'first_name': Parameter(str, 'First name'),
        'last_name': Parameter(str, 'Last name'),
        'phone': Parameter(str, 'Phone Number'),
        'keys': Parameter(str, 'Public key'),
        'slices': Parameter([str], 'List of slices this user belongs to'),
        }
    fields.update(SfaRecord.fields)
    
class SliceRecord(SfaRecord):
    fields = {
        'name': Parameter(str, 'Slice name'),
        'url': Parameter(str, 'Slice url'),
        'expires': Parameter(int, 'Date and time this slice exipres'),
        'researcher': Parameter([str], 'List of users for this slice'),
        'PI': Parameter([str], 'List of PIs responsible for this slice'),
        'description': Parameter([str], 'Description of this slice'), 
        }
    fields.update(SfaRecord.fields)

 
class NodeRecord(SfaRecord):
    fields = {
        'hostname': Parameter(str, 'This nodes dns name'),
        'node_type': Parameter(str, 'Type of node this is'),
        'node_type': Parameter(str, 'Type of node this is'),
        'latitude': Parameter(str, 'latitude'),
        'longitude': Parameter(str, 'longitude'),
        }
    fields.update(SfaRecord.fields)


class AuthorityRecord(SfaRecord):
    fields =  {
        'name': Parameter(str, 'Name'),
        'login_base': Parameter(str, 'login base'),
        'enabled': Parameter(bool, 'Is this site enabled'),
        'url': Parameter(str, 'URL'),
        'nodes': Parameter([str], 'List of nodes at this site'),  
        'operator': Parameter([str], 'List of operators'),
        'researcher': Parameter([str], 'List of researchers'),
        'PI': Parameter([str], 'List of Principal Investigators'),
        }
    fields.update(SfaRecord.fields)
    

