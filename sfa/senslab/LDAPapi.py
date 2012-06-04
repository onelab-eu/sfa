
import string
from sfa.util.xrn import Xrn,get_authority 
import ldap
from sfa.util.config import Config
#from sfa.trust.gid import *
from sfa.trust.hierarchy import Hierarchy
#from sfa.trust.auth import *
from sfa.trust.certificate import *
import ldap.modlist as modlist
from sfa.util.sfalogging import logger

class ldap_co:
    """ Set admin login and server configuration variables."""
    def __init__(self):
        
        self.login = 'cn=admin,dc=senslab,dc=info'
        self.passwd = 'sfa'  
        self.server_ip = "192.168.0.251"

    
    def connect(self, bind = True):
        """Enables connection to the LDAP server.
        Set the bind parameter to True if a bind is needed
        (for add/modify/delete operations).
        Set to False otherwise.
        
        """
        try:
            self.ldapserv = ldap.open(self.server_ip)
        except ldap.LDAPError, e:
            return {'bool' : False, 'message' : e }
        
        # Bind with authentification
        if(bind): 
            return self.bind()
        
        else:     
            return {'bool': True}
    
    
    def bind(self):
        """ Binding method. """
        try:
            # Opens a connection after a call to ldap.open in connect:
            self.ldapserv = ldap.initialize("ldap://" + self.server_ip )
                
            # Bind/authenticate with a user with apropriate rights to add objects
            self.ldapserv.simple_bind_s(self.login, self.passwd)

        except ldap.LDAPError, e:
            return {'bool' : False, 'message' : e }

        return {'bool': True}
    
    def close(self):
        """ Close the LDAP connection """
        try:
            self.ldapserv.unbind_s()
        except ldap.LDAPError, e:
            return {'bool' : False, 'message' : e }
            
        
class LDAPapi :
	def __init__(self):
            
                #SFA related config
		self.senslabauth=Hierarchy()
		config=Config()
		self.authname=config.SFA_REGISTRY_ROOT_AUTH
		#authinfo=self.senslabauth.get_auth_info(self.authname)
	

		#self.auth=Auth()
		#gid=authinfo.get_gid_object()
                #self.ldapdictlist = ['type',
                                #'pkey',
                                #'uid',
				#'serial',
				#'authority',
				#'peer_authority',
				#'pointer' ,
				#'hrn']
                self.baseDN = "ou=people,dc=senslab,dc=info"
                self.conn =  ldap_co()    
                          
	
        def generate_login(self, record):
            """Generate login for adding a new user in LDAP Directory 
            (four characters minimum length)
            Record contains first name and last name.
            
            """ 
            #Remove all special characters from first_name/last name
            lower_first_name = record['first_name'].replace('-','')\
                                            .replace('_','').replace('[','')\
                                            .replace(']','').replace(' ','')\
                                            .lower()
            lower_last_name = record['last_name'].replace('-','')\
                                            .replace('_','').replace('[','')\
                                            .replace(']','').replace(' ','')\
                                            .lower()  
            length_last_name = len(lower_last_name)
            login_max_length = 8
            
            #Try generating a unique login based on first name and last name
            getAttrs = ['uid']
            if length_last_name >= login_max_length :
                login = lower_last_name[0:login_max_length]
                index = 0;
                logger.debug("login : %s index : %s" %login %index);
            elif length_last_name >= 4 :
                login = lower_last_name
                index = 0
                logger.debug("login : %s index : %s" %login %index);
            elif length_last_name == 3 :
                login = lower_first_name[0:1] + lower_last_name
                index = 1
                logger.debug("login : %s index : %s" %login %index);
            elif length_last_name == 2:
                if len ( lower_first_name) >=2:
                    login = lower_first_name[0:2] + lower_last_name
                    index = 2
                    logger.debug("login : %s index : %s" %login %index);
                else:
                    logger.error("LoginException : \
                                Generation login error with \
                                minimum four characters")
                
                    
            else :
                logger.error("LDAP generate_login failed : \
                                impossible to generate unique login for %s %s" \
                                %lower_first_name %lower_last_name)
                
            filter = '(uid='+ login+ ')'
            try :
                #Check if login already in use
                while (self.ldapSearch(filter, getAttrs) is not [] ):
                
                    index += 1
                    if index >= 9:
                        logger.error("LoginException : Generation login error \
                                        with minimum four characters")
                    else:
                        try:
                            login = lower_first_name[0,index] + \
                                        lower_last_name[0,login_max_length-index]
                            filter = '(uid='+ login+ ')'
                        except KeyError:
                            print "lower_first_name - lower_last_name too short"
                return login
                        
            except  ldap.LDAPError,e :
                logger.log_exc("LDAP generate_login Error %s" %e)
                #print >>sys.stderr, "ERROR LDAP %s" %(e)   
            
            
        def find_max_uidNumber(self):
                
            """Find the LDAP max uidNumber (POSIX uid attribute) .
            Used when adding a new user in LDAP Directory 
            returns integer max uidNumber + 1
            
            """
            #Get all the users in the LDAP
            ldapUserUidNumberMin = 2000 

            getAttrs = "(uidNumber=*)"
            filter = ['uidNumber']

            result_data = self.ldapSearch(getAttrs, filter) 
            #First LDAP user
            if result_data == []:
                max_uidnumber = ldapUserUidNumberMin
            #Get the highest uidNumber
            else:
                uidNumberList = [r[1]['uidNumber'] for r in result_data ]
                max_uidnumber = max(uidNumberList) + 1
                
            return max_uidnumber
                       
	   
	def make_ldap_attributes_from_record(self, record):
            """When addind a new user to LDAP, creates an attributes dictionnary
            from the SFA record.
            
            """

            attrs = {}
            attrs['objectClass'] = ["top", "person", "inetOrgPerson",\
                                     "organizationalPerson", "posixAccount",\
                                     "shadowAccount", "systemQuotas",\
                                     "ldapPublicKey"]
            
            attrs['givenName'] = str(record['first_name']).lower(),capitalize()
            attrs['sn'] = str(record['last_name']).lower().capitalize()
            attrs['cn'] = attrs['givenName'] + ' ' + attrs['sn']
            attrs['gecos'] = attrs['givenName'] + ' ' + attrs['sn']
            attrs['uid'] = self.generate_login(record)   
                        
            attrs['quota'] = '/dev/vdb:2000000:2500000:0:0'
            attrs['homeDirectory'] = '/senslab/users/' + attrs['uid']
            attrs['loginShell'] = '/senslab/users/.ssh/welcome.sh'
            attrs['gidNumber'] = '2000'	
            attrs['uidNumber'] = str(self.find_max_uidNumber())
            attrs['mail'] = record['mail'].lower()
            attrs['sshPublicKey'] = record['sshpkey']  #To be filled by N. Turro
            attrs['description'] = 'SFA USER FROM OUTSIDE SENSLAB'
            #TODO  TO BE FILLED 
            attrs['userPassword']= ""
            
            return attrs
        
        def ldapAdd(self, record = None) :
            """Add SFA user to LDAP """
           
            user_ldap_attrs = self.make_ldap_attributes_from_record(record)
            #Bind to the server
            result = self.conn.connect()
            
            if(result['bool']):
                
                # A dict to help build the "body" of the object
                
                logger.debug(" \r\n \t LDAP ldapAdd attrs %s " %user_ldap_attrs)

                # The dn of our new entry/object
                dn = 'uid=' + user_ldap_attrs['uid'] + "," + self.baseDN 
 
                try:
                    ldif = modlist.addModlist(user_ldap_attrs)
                    logger.debug("\r\n \tLDAPapi.PY add attrs %s \r\n  ldif %s"\
                                 %(user_ldap_attrs,ldif) )
                    self.conn.ldapserv.add_s(dn,ldif)
                    
                    logger.info("Adding user %s login %s in LDAP" \
                            %user_ldap_attrs['cn'] %user_ldap_attrs['uid'])
                            
                            
                except ldap.LDAPError, e:
                    logger.log_exc("LDAP Add Error %s" %e)
                    return {'bool' : False, 'message' : e }
            
                self.conn.close()
                return {'bool': True}  
            else: 
                return result

         
        def ldapDelete(self, person_dn):
            """
            Deletes a person in LDAP. Uses the dn of the user.
            """
            #Connect and bind   
            result =  self.conn.connect()
            if(result['bool']):
                try:
                    self.conn.ldapserv.delete_s(person_dn)
                    self.conn.close()
                    return {'bool': True}
                
                except ldap.LDAPError, e:
                    logger.log_exc("LDAP Delete Error %s" %e)
                    return {'bool': False}
            
        
        def ldapDeleteHrn(self, record_filter): 
            """
            Deletes a SFA person in LDAP, based on the user's hrn.
            """
            #Find uid of the  person 
            person = self.ldapFindHrn(record_filter)
           
            if person:
                dn = 'uid=' + person['uid'] + "," +self.baseDN 
            else:
                return {'bool': False}
            
            result = self.ldapDelete(dn)
            return result
            
                    
                    
        def ldapModify(self, record_filter, new_attributes):
            """
            Gets the record from one user based on record_filter 
            and changes the attributes according to the specified new_attributes.
            Does not use this if we need to modify the uid. Use a ModRDN 
            #operation instead ( modify relative DN )
            """
            
            person = self.ldapFindHrn(record_filter,[] )
            if person:
                # The dn of our existing entry/object
                dn  = 'uid=' + person['uid'] + "," +self.baseDN 
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
                        self.conn.close()
                    except ldap.LDAPError, e:
                        logger.log_exc("LDAP ldapModify Error %s" %e)
                        return {'bool' : False }
                
                return {'bool': True}  
                
                
                
        #TODO Handle OR filtering in the ldap query when 
        #dealing with a list of records instead of doing a for loop in GetPersons   
        def make_ldap_filters_from_record(self, record=None):
            """
            Helper function to make LDAP filter requests out of SFA records.
            """
            req_ldapdict = {}
            if record :
                if 'first_name' in record  and 'last_name' in record:
                    req_ldapdict['cn'] = str(record['first_name'])+" "\
                                            + str(record['last_name'])
                if 'email' in record :
                    req_ldapdict['mail'] = record['email']
                if 'hrn' in record :
                    splited_hrn = record['hrn'].split(".")
                    if splited_hrn[0] != self.authname :
                        logger.warning(" \r\n LDAP.PY \
                            make_ldap_filters_from_record I know nothing \
                            about %s my authname is %s not %s" \
                            %(record['hrn'], self.authname, splited_hrn[0]) )
                            
                    login=splited_hrn[1]
                    req_ldapdict['uid'] = login
                
                req_ldap=''
                logger.debug("\r\n \t LDAP.PY make_ldap_filters_from_record \
                                    record %s req_ldapdict %s" \
                                    %(record, req_ldapdict))
               
                for k in req_ldapdict:
                    req_ldap += '('+str(k)+'='+str(req_ldapdict[k])+')'
                if  len(req_ldapdict.keys()) >1 :
                    req_ldap = req_ldap[:0]+"(&"+req_ldap[0:]
                    size = len(req_ldap)
                    req_ldap= req_ldap[:(size-1)] +')'+ req_ldap[(size-1):]
            else:
                req_ldap = "(cn=*)"
            
            return req_ldap

            
            

	def ldapSearch (self, req_ldap = None, expected_fields = None ):
            """
            Used to search directly in LDAP, by using ldap filters and
            return fields. 
            When req_ldap is None, returns all the entries in the LDAP.
            """
            result = self.conn.connect(bind = False)
            if (result['bool']) :
                
                return_fields = []
                if expected_fields == None : 
                    return_fields = ['mail','givenName', 'sn', 'uid','sshPublicKey']
                else : 
                    return_fields = expected_fields
                    
                logger.debug("LDAP.PY \t ldapSearch  req_ldap %s \
                                return_fields %s" %(req_ldap,return_fields))
    
                try:
                    msg_id = self.conn.ldapserv.search(
                                                self.baseDN,ldap.SCOPE_SUBTREE,\
                                                req_ldap,return_fields)     
                    #Get all the results matching the search from ldap in one 
                    #shot (1 value)
                    result_type, result_data = \
                                         self.conn.ldapserv.result(msg_id,1)

                    self.conn.close()

                    logger.debug("LDAP.PY \t ldapSearch  result_data %s"\
                                %(result_data))
    
                    return result_data
                
                except  ldap.LDAPError,e :
                    logger.log_exc("LDAP ldapSearch Error %s" %e)
                    return []
                
                else:
                    logger.error("LDAP.PY \t Connection Failed" )
                    return 
               

        def ldapFindHrn(self,record = None, expected_fields = None):
            """
            Search a SFA user with a hrn. User should be already registered 
            in Senslab LDAP. 
            Returns one matching entry 
            """   

            req_ldap = self.make_ldap_filters_from_record(record) 
            return_fields = []
            if expected_fields == None : 
               return_fields = ['mail','givenName', 'sn', 'uid','sshPublicKey']
            else : 
                return_fields = expected_fields
                
            result_data = self.ldapSearch(req_ldap,  return_fields )
               
            if result_data is None:
                    return None
            #Asked for a specific user
            if record :
                ldapentry = result_data[0][1]
                logger.debug("LDAP.PY \t ldapFindHrn ldapentry %s" %(ldapentry))
                tmpname = ldapentry['uid'][0]

                tmpemail = ldapentry['mail'][0]
                if ldapentry['mail'][0] == "unknown":
                    tmpemail = None
                    
                try:
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
                except KeyError:
                    lorrer.log_exc("LDAPapi \t ldapSearch KEyError results %s" \
                                   %(results) )
                    pass 
            else:
            #Asked for all users in ldap
                results = []
                for ldapentry in result_data:
                    logger.debug(" LDAP.py ldapFindHrn ldapentry name : %s " \
                                 %(ldapentry[1]['uid'][0]))
                    tmpname = ldapentry[1]['uid'][0]
                    hrn=self.authname+"."+ tmpname
                    
                    tmpemail = ldapentry[1]['mail'][0]
                    if ldapentry[1]['mail'][0] == "unknown":
                        tmpemail = None

            
                    parent_hrn = get_authority(hrn)
                    parent_auth_info = self.senslabauth.get_auth_info(parent_hrn)
                    try:
                        results.append(  {	
                                'type': 'user',
                                'pkey': ldapentry[1]['sshPublicKey'][0],
                                #'uid': ldapentry[1]['uid'][0],
                                'uid': tmpname ,
                                'email':tmpemail,
                                #'email': ldapentry[1]['mail'][0],
                                'first_name': ldapentry[1]['givenName'][0],
                                'last_name': ldapentry[1]['sn'][0],
                                #'phone': 'none',
                                'serial': 'none',
                                'authority': self.authname,
                                'peer_authority': '',
                                'pointer' : -1,
                                'hrn': hrn,
                                } ) 
                    except KeyError:
                        pass
            return results   
                
