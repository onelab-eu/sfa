
import string
from sfa.util.xrn import Xrn,get_authority 
import ldap
from sfa.util.config import *
from sfa.trust.gid import *
from sfa.trust.hierarchy import *
from sfa.trust.auth import *
from sfa.trust.certificate import *
import ldap.modlist as modlist

class ldap_co:
    def __init__(self):
    #def __init__(self, param, level):
        """
        Constructeur permettant l'initialisation des attributs de la classe
        :param param: Parametres de connexion au serveur LDAP
        :type param: dictionnary.
        :param level: Niveau de criticite de l'execution de l'objet ('critical, warning')
        :type level: string.
        """

        self.__level = 'warning'
        #self.__param = param
        #self.__level = level
        self.login = 'cn=admin,dc=senslab,dc=info'
    
        self.passwd='sfa'  
        print "\r\n INIT OK !"
    
    def connect(self, bind = True):
        """
        Methode permettant la connexion a un serveur LDAP
        @param bool bind : Force ou non l'authentification au serveur
        @return array : Retour d'un tableau
        """
        try:
            self.ldapserv = ldap.open("192.168.0.251")
        except ldap.LDAPError, e:
            return {'bool' : False, 'message' : e }
        
        # Bind non anonyme avec authentification
        if(bind): 
            return self.bind()
        
        else:     
            return {'bool': True}
    
    
    def bind(self):
        """
        Methode permettant l'authentification a un serveur LDAP
        @return array : Retour d'un tableau
        """
        try:
            print "\r\n BIND ??!"
            # Open a connection
            self.ldapserv = ldap.initialize("ldap://192.168.0.251")    
            # Bind/authenticate with a user with apropriate rights to add objects
            self.ldapserv.simple_bind_s(self.login, self.passwd)
            print "\r\n BIND ???"
        except ldap.LDAPError, e:
            return {'bool' : False, 'message' : e }
        
        print "\r\n BIND OK !"
        return {'bool': True}
    
    def close(self):
        """
        Methode permettant la deconnexion a un serveur LDAP
        """
        # Fermeture de la connexion
        try:
            self.ldapserv.unbind_s()
        except ldap.LDAPError, e:
            pass
            
        
class LDAPapi :
	def __init__(self):
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
                self.conn =  ldap_co()    
                          

                              
        def ldapAdd(self, recordix = None) :
            #SFA users are added from here
            #They get a uidNumber range 9000 - 9999 (recerved for SFA)
            #They get a description attribute which others don't have.
            result = self.conn.connect(bind = False)
            if (result['bool']): 
                #Find all the external SFA users in the LDAP
                msgid = self.conn.ldapserv.search(ldap.baseDN,D.SCOPE_SUBTREE,"(description=*)",[]) 
                result_type, result_data = self.conn.ldapserv.result(msg_id,1)
                #First external SFA user
                if result_data == []:
                    max_uidnumber = 9000
                #Get the highest uidNumber
                else:
                    max_uidnumber = 0
                    for r in result_data:
                        if r[1]['uidNumber'] > max_uidnumber :
                            max_uidnumber = r[1]['uidNumber']
                    max_uidnumber =   max_uidnumber +1
            
            result = self.conn.connect()
            if(result['bool']):
                print >>sys.stderr, "\r\n \r\n \t LDAP.PY \t\t  ldapAdd  attrs %s " %(attrs)
                # A dict to help build the "body" of the object
                attrs = {}
                attrs['uidNumber'] = str(max_uidnumber)
                attrs['objectclass'] = ['top','inetOrgPerson','posixAccount', 'systemQuotas','ldapPuclicKey']
                attrs['cn'] = str(record['first_name'])+' ' + str(record['last_name'])
                attrs['sn'] = str(record['last_name'])
                attrs['givenName'] = str(record['first_name'])
                attrs['gidNumber'] = '2000'
                loginslab =str(record['first_name'])+ str(record['last_name'])
                loginslab= loginslab.lower()
                #loginslab  = loginslab[0:12]
                attrs['uid']= loginslab
                attrs['mail'] = record['mail']
                attrs['quota'] = '/dev/sda3:2000000:2500000:0:0'
                attrs['homeDirectory'] = '/senslab/users/' + loginslab
                attrs['loginShell'] = '/senslab/users/.ssh/welcome.sh'
                attrs['sshPublicKey'] = ''
                attrs['description'] = 'SFA USER FROM OUTSIDE SENSLAB'
                
                # The dn of our new entry/object
                dn = 'uid=' +attrs['uid'] +","+self.baseDN 
 
                try:
                        ldif = modlist.addModlist(attrs)
                        print " \r\n \r\n LDAPTEST.PY add attrs %s \r\n  ldif %s  " %(attrs,ldif) 
                        self.conn.ldapserv.add_s(dn,ldif)

                except ldap.LDAPError, e:
                    return {'bool' : False, 'message' : e }
            
                self.close()
                return {'bool': True}  
            else: 
                return result
                return  
         
         
        def ldapDelete(self, record_filter): 
            #Find uid of the  person 
            person = self.ldapSearch(record_filter, ['uid'])
           
            if person:
                dn = 'uid=' +person['uid'] +","+self.baseDN 
            else:
                return {'bool': False}
            
            #Connect and bind   
            result =  self.conn.connect()
            if(result['bool']):
                try:
                    self.conn.ldapserv.delete_s(dn)
                    return {'bool': True}
                
                except ldap.LDAPError, e:
                    print>>sys.stderr, "\r\n LDAP.PY \tldapDelete error : %s" %(e)  
                    return {'bool': False}
                    
                    
        def ldapModify(self, record_filter, new_attributes):
            """
            Gets the record from one user based on record_filter 
            and changes the attributes according to the specified new_attributes.
            Does not use this if we need to modify the uid. Use a ModRDMN 
            #operation instead ( modify relative DN )
            """
            
            person = self.ldapSearch(record_filter,[] )
            if person:
                # The dn of our existing entry/object
                dn  = 'uid=' +person['uid'] +","+self.baseDN 
            else:
                return
            
            if new_attributes:
                old = {}
                for k in new_attributes:
                    old[k] =  person[k]
                    
                ldif = modlist.modifyModlist(old,new_attributes)
                
                # Connect and bind/authenticate    
                result = self.conn.connect(bind) 
                if (result['bool']): 
                    try:
                        self.conn.ldapserver.modify_s(dn,ldif)
                        self.close()
                    except ldap.LDAPError, e:
                        return {'bool' : False, 'message' : e }
                return {'bool': True}  
                
                
                
        #TODO Handle OR filtering in the ldap query when 
        #dealing with a list of records instead of doing a for loop in GetPersons                                  
        def make_ldap_filters_from_record(self, record=None):
            
            req_ldapdict = {}
            if record :
                if 'first_name' in record  and 'last_name' in record:
                    req_ldapdict['cn'] = str(record['first_name'])+" "+str(record['last_name'])
                if 'email' in record :
                    req_ldapdict['mail'] = record['email']
                if 'hrn' in record :
                    splited_hrn = record['hrn'].split(".")
                    if splited_hrn[0] != self.authname :
                            print >>sys.stderr,"i know nothing about",record['hrn'], " my authname is ", self.authname, " not ", splited_hrn[0]
                    login=splited_hrn[1]
                    req_ldapdict['uid'] = login
                
                req_ldap=''
                print >>sys.stderr, "\r\n \r\n \t LDAP.PY \t\t   make_ldap_filters_from_record record %s req_ldapdict %s" %(record,req_ldapdict)
                for k in req_ldapdict:
                    req_ldap += '('+str(k)+'='+str(req_ldapdict[k])+')'
                if  len(req_ldapdict.keys()) >1 :
                    req_ldap = req_ldap[:0]+"(&"+req_ldap[0:]
                    size = len(req_ldap)
                    req_ldap= req_ldap[:(size-1)] +')'+ req_ldap[(size-1):]
            else:
                req_ldap = "(cn*)"
            
            return req_ldap

            
            
        #Returns one matching entry                                
	def ldapSearch (self, record = None, expected_fields = None ):
            
            self.conn.connect(bind = False)
            #self.connect()
            req_ldap = self.make_ldap_filters_from_record(record)
            if expected_fields == None : 
               return_fields = ['mail','givenName', 'sn', 'uid','sshPublicKey']
            print >>sys.stderr, "\r\n \r\n \t LDAP.PY \t\t ldapSearch  req_ldap %s" %(req_ldap)
            try:
                msg_id=self.conn.ldapserv.search(self.baseDN,ldap.SCOPE_SUBTREE,req_ldap,return_fields)     
                #Get all the results matching the search from ldap in one shot (1 value)
                result_type, result_data = self.conn.ldapserv.result(msg_id,1)
                #results = []
                print >>sys.stderr, "\r\n \r\n \t LDAP.PY \t\t ldapSearch  result_data %s" %(result_data) 
                
                #Asked for a specific user
                if record:
                    ldapentry = result_data[0][1]
                    print >>sys.stderr, "\r\n \r\n \t LDAP.PY \t\t ldapSearch  ldapentry %s" %(ldapentry) 
                    tmpname = ldapentry['uid'][0]
   
                    tmpemail = ldapentry['mail'][0]
                    if ldapentry['mail'][0] == "unknown":
                        tmpemail = None
                        
                    hrn = record['hrn']
                    parent_hrn = get_authority(hrn)
                    peer_authority = None
                    if parent_hrn is not self.authname:
                        peer_authority = parent_hrn
                            

                                    
                    results=  {	
                                'type': 'user',
                                'pkey': ldapentry['sshPublicKey'][0],
                                #'uid': ldapentry[1]['uid'][0],
                                'uid': tmpname ,
                                'email':tmpemail,
                                #'email': ldapentry[1]['mail'][0],
                                'first_name': ldapentry['givenName'][0],
                                'last_name': ldapentry['sn'][0],
                                #'phone': 'none',
                                'serial': 'none',
                                'authority': parent_hrn,
                                'peer_authority': peer_authority,
                                'pointer' : -1,
                                'hrn': hrn,
                                } 
		else:
                #Asked for all users in ldap
                    results = []
                    for ldapentry in result_data[1]:
                         
                        tmpname = ldapentry[1]['uid'][0]
                        
                        if ldapentry[1]['uid'][0] == "savakian":
                            tmpname = 'avakian'

			hrn=self.authname+"."+ tmpname
                        
                        tmpemail = ldapentry[1]['mail'][0]
                        if ldapentry[1]['mail'][0] == "unknown":
                            tmpemail = None

		
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

            
            except  ldap.LDAPError,e :
                print >>sys.stderr, "ERROR LDAP %s" %(e)
               
        

        
	#def ldapFindHrn(self, record_filter = None):        
	##def ldapFindHrn(self, record_filter = None, columns=None):

 		#results = [] 
                #self.conn.connect(bind = False)
	        ##self.connect()
		#if 'authority' in record_filter:
		## ask for authority
			#if record_filter['authority']==self.authname:
				## which is SFA_REGISTRY_ROOT_AUTH
				## request all records which are under our authority, ie all ldap entries
				#ldapfilter="cn=*"
			#else:
				##which is NOT SFA_REGISTRY_ROOT_AUTH
				#return []
		#else :
			#if not 'hrn' in record_filter:
				#print >>sys.stderr,"find : don't know how to handle filter ",record_filter
				#return []
			#else:
				#hrns=[]
				#h=record_filter['hrn']
				#if  isinstance(h,list):
					#hrns=h
				#else : 
					#hrns.append(h)
	
				#ldapfilter="(|"
				#for hrn in hrns:
					#splited_hrn=hrn.split(".")
					#if splited_hrn[0] != self.authname :
						#print >>sys.stderr,"i know nothing about",hrn, " my authname is ", self.authname, " not ", splited_hrn[0]
					#else :
						#login=splited_hrn[1]
						#ldapfilter+="(uid="
						#ldapfilter+=login
						#ldapfilter+=")"
				#ldapfilter+=")"
	
                #rindex=self.conn.ldapserv.search(self.baseDN,ldap.SCOPE_SUBTREE,ldapfilter, ['mail','givenName', 'sn', 'uid','sshPublicKey'])
		##rindex=self.ldapserv.search(self.baseDN,ldap.SCOPE_SUBTREE,ldapfilter, ['mail','givenName', 'sn', 'uid','sshPublicKey'])
		#ldapresponse=self.conn.ldapserv.result(rindex,1)
		#for ldapentry in ldapresponse[1]:
                         
                        #tmpname = ldapentry[1]['uid'][0]
                        
                        #if ldapentry[1]['uid'][0] == "savakian":
                            #tmpname = 'avakian'

			#hrn=self.authname+"."+ tmpname
                        
                        #tmpemail = ldapentry[1]['mail'][0]
                        #if ldapentry[1]['mail'][0] == "unknown":
                            #tmpemail = None
##			uuid=create_uuid() 
		
##			RSA_KEY_STRING=ldapentry[1]['sshPublicKey'][0]
		
##			pkey=convert_public_key(RSA_KEY_STRING)
		
##			gid=self.senslabauth.create_gid("urn:publicid:IDN+"+self.authname+"+user+"+ldapentry[1]['uid'][0], uuid, pkey, CA=False)
		
			#parent_hrn = get_authority(hrn)
			#parent_auth_info = self.senslabauth.get_auth_info(parent_hrn)

			#results.append(  {	
				#'type': 'user',
                                #'pkey': ldapentry[1]['sshPublicKey'][0],
                                ##'uid': ldapentry[1]['uid'][0],
                                #'uid': tmpname ,
                                #'email':tmpemail,
				##'email': ldapentry[1]['mail'][0],
				#'first_name': ldapentry[1]['givenName'][0],
				#'last_name': ldapentry[1]['sn'][0],
##				'phone': 'none',
				#'serial': 'none',
				#'authority': self.authname,
				#'peer_authority': '',
				#'pointer' : -1,
				#'hrn': hrn,
			 	#} )
		#return results
