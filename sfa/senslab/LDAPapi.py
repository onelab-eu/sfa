


import ldap
from sfa.util.config import *
from sfa.trust.gid import *
from sfa.trust.hierarchy import *
from sfa.trust.auth import *
from sfa.trust.certificate import *

class LDAPapi :
	def __init__(self, record_filter = None):
		self.ldapserv=ldap.open("192.168.0.251")
		self.senslabauth=Hierarchy()
		config=Config()
		self.authname=config.SFA_REGISTRY_ROOT_AUTH
		authinfo=self.senslabauth.get_auth_info(self.authname)
	
		self.auth=Auth()
		gid=authinfo.get_gid_object()
	
	def ldapFind(self, record_filter = None, columns=None):

 		results = []
	
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
					if splited_hrn[0] != self.authname :
						print >>sys.stderr,"i know nothing about",hrn, " my authname is ", self.authname, " not ", splited_hrn[0]
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
#			uuid=create_uuid() 
		
#			RSA_KEY_STRING=ldapentry[1]['sshPublicKey'][0]
		
#			pkey=convert_public_key(RSA_KEY_STRING)
		
#			gid=self.senslabauth.create_gid("urn:publicid:IDN+"+self.authname+"+user+"+ldapentry[1]['uid'][0], uuid, pkey, CA=False)
		
			parent_hrn = get_authority(hrn)
			parent_auth_info = self.senslabauth.get_auth_info(parent_hrn)

			results.append(  {	
				'type': 'user',
                                'pkey': ldapentry[1]['sshPublicKey'][0].
#				'email': ldapentry[1]['mail'][0],
#				'first_name': ldapentry[1]['givenName'][0],
#				'last_name': ldapentry[1]['sn'][0],
#				'phone': 'none',
				'serial': 'none',
				'authority': self.authname,
				'peer_authority': '',
				'pointer' : -1,
				'hrn': hrn,
			 	} )
		return results
