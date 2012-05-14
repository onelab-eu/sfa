

from sfa.util.xrn import Xrn,get_authority, 
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
                self.ldapdictlist = ['type',
                                'pkey',
                                'uid',
				'serial',
				'authority',
				'peer_authority',
				'pointer' ,
				'hrn']
                self.baseDN = "ou=people,dc=senslab,dc=info"
                                
	def ldapSearch (self, record ):
            
            req_ldapdict = {}

            if 'first_name' in record  and 'last_name' in record:
                req_ldapdict['cn'] = str(record['first_name'])+" "+str(record['last_name'])
            if 'email' in record :
                req_ldapdict['mail'] = record['email']

            for k in req_ldapdict:
                req_ldap += '('+str(k)+'='+str(req_ldapdict['k'])+')'
            if  len(req_ldapdict.keys()) >1 :
                req_ldap = req_ldap[:0]+"(&"+req_ldap[0:]
                size = len(req_ldap)
                req_ldap= req_ldap[:(size-1)] +')'+ req_ldap[(size-1):]
            print >>sys.stderr, "\r\n \r\n \t LDAP.PY \t\t ldapSearch  req_ldap %s" %(req_ldap)
            try:
                msg_id=self.ldapserv.search(self.baseDN,ldap.SCOPE_SUBTREE,req_ldap, ['mail','givenName', 'sn', 'uid','sshPublicKey'])     
                #Get all the results matching the search from ldap in one shot (1 value)
                result_type, result_data=self.ldapserv.result(msg_id,1)
                results = []
                for ldapentry in result_data[1]:
                        #print>>sys.stderr, " \r\n \t LDAP : ! mail ldapentry[1]['mail'][0] %s " %(ldapentry[1]['mail'][0])
                         
                        tmpname = ldapentry[1]['uid'][0]
                        
                        if ldapentry[1]['uid'][0] == "savakian":
                            tmpname = 'avakian'

                        tmpemail = ldapentry[1]['mail'][0]
                        if ldapentry[1]['mail'][0] == "unknown":
                            tmpemail = None
                            
                        hrn = record['hrn']
                        parent_hrn = get_authority(hrn)
                        peer_authority = None
                        if parent_hrn is not self.authname:
                            peer_authority = parent_hrn
                        
			results.append(  {	
				'type': 'user',
                                'pkey': ldapentry[1]['sshPublicKey'][0],
                                #'uid': ldapentry[1]['uid'][0],
                                'uid': tmpname ,
                                'email':tmpemail,
				#'email': ldapentry[1]['mail'][0],
				'first_name': ldapentry[1]['givenName'][0],
				'last_name': ldapentry[1]['sn'][0],
#				'phone': 'none',
				'serial': 'none',
				'authority': parent_hrn,
				'peer_authority': peer_authority,
				'pointer' : -1,
				'hrn': hrn,
			 	} )
		return results

            
            except  ldap.LDAPError,e :
                print >>sys.stderr, "ERROR LDAP %s" %(e)
               
        
            
	def ldapFindHrn(self, record_filter = None):        
	#def ldapFindHrn(self, record_filter = None, columns=None):

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
	
	
		rindex=self.ldapserv.search(self.baseDN,ldap.SCOPE_SUBTREE,ldapfilter, ['mail','givenName', 'sn', 'uid','sshPublicKey'])
		ldapresponse=self.ldapserv.result(rindex,1)
		for ldapentry in ldapresponse[1]:
                        #print>>sys.stderr, " \r\n \t LDAP : ! mail ldapentry[1]['mail'][0] %s " %(ldapentry[1]['mail'][0])
                         
                        tmpname = ldapentry[1]['uid'][0]
                        
                        if ldapentry[1]['uid'][0] == "savakian":
                            tmpname = 'avakian'

			hrn=self.authname+"."+ tmpname
                        
                        tmpemail = ldapentry[1]['mail'][0]
                        if ldapentry[1]['mail'][0] == "unknown":
                            tmpemail = None
#			uuid=create_uuid() 
		
#			RSA_KEY_STRING=ldapentry[1]['sshPublicKey'][0]
		
#			pkey=convert_public_key(RSA_KEY_STRING)
		
#			gid=self.senslabauth.create_gid("urn:publicid:IDN+"+self.authname+"+user+"+ldapentry[1]['uid'][0], uuid, pkey, CA=False)
		
			parent_hrn = get_authority(hrn)
			parent_auth_info = self.senslabauth.get_auth_info(parent_hrn)

			results.append(  {	
				'type': 'user',
                                'pkey': ldapentry[1]['sshPublicKey'][0],
                                #'uid': ldapentry[1]['uid'][0],
                                'uid': tmpname ,
                                'email':tmpemail,
				#'email': ldapentry[1]['mail'][0],
				'first_name': ldapentry[1]['givenName'][0],
				'last_name': ldapentry[1]['sn'][0],
#				'phone': 'none',
				'serial': 'none',
				'authority': self.authname,
				'peer_authority': '',
				'pointer' : -1,
				'hrn': hrn,
			 	} )
		return results
