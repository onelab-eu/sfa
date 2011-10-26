#
# implements support for SFA records stored in db tables
#
# TODO: Use existing PLC database methods? or keep this separate?

import ldap
from sfa.trust.gid import *
from sfa.util.record import *
from sfa.util.config import *
from sfa.util.filter import *
from sfa.trust.hierarchy import *
from sfa.trust.certificate import *
from sfa.trust.auth import *
from sfa.senslab.OARrestapi import *

class SfaTable(list):
    authname=""
    def __init__(self, record_filter = None):
	self.oar = OARapi()
        self.ldapserv=ldap.open("192.168.0.251")
	self.senslabauth=Hierarchy()
	config=Config()
	self.authname=config.SFA_REGISTRY_ROOT_AUTH
	print >>sys.stderr,"AUTHNAME :  ",self.authname
	authinfo=self.senslabauth.get_auth_info(self.authname)
	
	self.auth=Auth()
	gid=authinfo.get_gid_object()

    def exists(self):
        return True

    def db_fields(self, obj=None):
        return dict( [ ] )

    @staticmethod
    def is_writable (key,value,dict):
        # if not mentioned, assume it's writable (e.g. deleted ...)
        if key not in dict: return True
        # if mentioned but not linked to a Parameter object, idem
        if not isinstance(dict[key], Parameter): return True
        # if not marked ro, it's writable
        if not dict[key].ro: return True

        return False


    def create(self):
        return True
    
    def remove(self, record):
        return 0

    def insert(self, record):
        return 0

    def update(self, record):
        return 0

    def quote_string(self, value):
        return str(self.db.quote(value))

    def quote(self, value):
        return self.db.quote(value)
    
    def ldapFind(self, record_filter = None, columns=None):

 	results = []
	
	#first, ldap for users

	if 'authority' in record_filter:
		# ask for authority
		if record_filter['authority']==self.authname:
			# which is SFA_REGISTRY_ROOT_AUTH
			# request all records which are under our authority, ie all ldap entries
			ldapfilter="cn=*"
		else:
			#which is NOT SFA_REGISTRY_ROOT_AUTH
			return []
	else :
		if not 'hrn' in record_filter:
			print >>sys.stderr,"find : don't know how to handle filter ",record_filter
			return []
		else:
			hrns=[]
			h=record_filter['hrn']
			if  isinstance(h,list):
				hrns=h
			else : 
				hrns.append(h)
	
			ldapfilter="(|"
			for hrn in hrns:
				splited_hrn=hrn.split(".")
				if splited_hrn[0] != "SFA_REGISTRY_ROOT_AUTH" :
					print >>sys.stderr,"i know nothing about",hrn
				else :
					login=splited_hrn[1]
					ldapfilter+="(uid="
					ldapfilter+=login
					ldapfilter+=")"
			ldapfilter+=")"
	
	
	rindex=self.ldapserv.search("ou=people,dc=senslab,dc=info",ldap.SCOPE_SUBTREE,ldapfilter, ['mail','givenName', 'sn', 'uid','sshPublicKey'])
	ldapresponse=self.ldapserv.result(rindex,1)
	for ldapentry in ldapresponse[1]:
		hrn=self.authname+"."+ldapentry[1]['uid'][0]
		uuid=create_uuid() 
		
		RSA_KEY_STRING=ldapentry[1]['sshPublicKey'][0]
		
		pkey=convert_public_key(RSA_KEY_STRING)
		
		gid=self.senslabauth.create_gid("urn:publicid:IDN+"+self.authname+"+user+"+ldapentry[1]['uid'][0], uuid, pkey, CA=False)
		
		parent_hrn = get_authority(hrn)
		parent_auth_info = self.senslabauth.get_auth_info(parent_hrn)

		results.append(  {	
			'type': 'user',
#			'email': ldapentry[1]['mail'][0],
#			'first_name': ldapentry[1]['givenName'][0],
#			'last_name': ldapentry[1]['sn'][0],
#			'phone': 'none',
			'gid': gid.save_to_string(),
			'serial': 'none',
			'authority': self.authname,
			'peer_authority': '',
			'pointer' : '',
			'hrn': hrn,
			'date_created' : 'none',
			'last_updated': 'none'
		 	} )
	return results

    def oarFind(self, record_filter = None, columns=None):
	results=[]
	node_ids=[]

	if 'authority' in record_filter:
		# ask for authority
		if record_filter['authority']== self.authname :
			# which is senslab
			print>> sys.stderr , "ET MERDE !!!!"
			node_ids=""
		else:
			# which is NOT senslab
			return []
	else :
		if not 'hrn' in record_filter:
			print >>sys.stderr,"find : don't know how to handle filter ",record_filter
			return []
		else:
			hrns=[]
			h=record_filter['hrn']
			if  isinstance(h,list):
				hrns=h
			else : 
				hrns.append(h)
	
			for hrn in hrns:
				head,sep,tail=hrn.partition(".")
				if head != self.authname :
					print >>sys.stderr,"i know nothing about",hrn
				else :
					node_ids.append(tail)

	node_list = self.oar.GetNodes( node_ids)

	for node in node_list:
		hrn=self.authname+"."+node['hostname']
		results.append(  {	
			'type': 'node',
#			'email': ldapentry[1]['mail'][0],
#			'first_name': ldapentry[1]['givenName'][0],
#			'last_name': ldapentry[1]['sn'][0],
#			'phone': 'none',
#			'gid': gid.save_to_string(),
#			'serial': 'none',
			'authority': self.authname,
			'peer_authority': '',
			'pointer' : '',
			'hrn': hrn,
			'date_created' : 'none',
			'last_updated': 'none'
		 	} )	
	
	return results
    
    def find(self, record_filter = None, columns=None):
	# senslab stores its users in an ldap dictionnary
        # and nodes in a oar scheduller database
        # both should be interrogated.
	print >>sys.stderr,"find : ",record_filter
	if not isinstance(record_filter,dict):
		print >>sys.stderr,"find : record_filter is not a dict"
		print >>sys.stderr,record_filter.__class__
		return []
	allResults=[]
	if 'type' in record_filter:
		if record_filter['type'] == 'slice':
			print >>sys.stderr,"find : don't know how to handle slices yet"
			return []
		if record_filter['type'] == 'authority':
			if  'hrn' in  record_filter and record_filter['hrn']==self.authname:
				return []
			else:
				print >>sys.stderr,"find which authority ?"
				return []
		if record_filter['type'] == 'user':
			return self.ldapFind(record_filter, columns)
		if record_filter['type'] == 'node':
			return self.ldapFind(record_filter, columns)
		else:
			print >>sys.stderr,"unknown type to find : ", record_filter['type']
			return []
	else:
		allResults = self.ldapFind(record_filter, columns)
		allResults+= self.oarFind(record_filter, columns)
	
	return allResults
    
    def findObjects(self, record_filter = None, columns=None):
 
	print >>sys.stderr,"find : ",record_filter
        #        print record_filter['type']
        #        if record_filter['type'] in  ['authority']:
        #            print "findObjectAuthority"
        results = self.find(record_filter, columns) 
        result_rec_list = []
	for result in results:
        	if result['type'] in ['authority']:
			result_rec_list.append(AuthorityRecord(dict=result))
		elif result['type'] in ['node']:
                	result_rec_list.append(NodeRecord(dict=result))
            	elif result['type'] in ['slice']:
                	result_rec_list.append(SliceRecord(dict=result))
             	elif result['type'] in ['user']:
                 	result_rec_list.append(UserRecord(dict=result))
             	else:
                 	result_rec_list.append(SfaRecord(dict=result))
	
	return result_rec_list


    def drop(self):
        return 0
    
    def sfa_records_purge(self):
        return 0
        
