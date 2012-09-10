###########################################################################
#    Copyright (C) 2012 by                                       
#    <savakian@sfa2.grenoble.senslab.info>                                                             
#
# Copyright: See COPYING file that comes with this distribution
#
###########################################################################
#LDAP import 
from sfa.senslab.LDAPapi import *
import ldap.modlist as modlist
import ldap as L

#logger sfa
from sfa.util.sfalogging import logger

#OAR imports
from datetime import datetime
from dateutil import tz 
from time import strftime,gmtime
from sfa.senslab.OARrestapi import OARrestapi

#Test slabdriver
from sfa.senslab.slabdriver import SlabDriver
from sfa.util.config import Config

import sys


        
def parse_options():
    
    #arguments supplied
    if len(sys.argv) > 1 :
        options_list = sys.argv[1:]
        #For each valid option, execute the associated function
        #(defined in the dictionnary supported_options)
        job_id = 1
        valid_options_dict = {}
        value_list = []
        #Passing options to the script should be done like this :
        #-10 OAR -2 SlabDriver
        for option in options_list:
            if option in supported_options:
                #update the values used for the fonctions associated 
                #with the options
                
                valid_options_dict[option] = value_list
                #empty the values list for next option
                value_list = []
                print valid_options_dict
            else:
                if option[0] == '-':
                    value_list.append(option[1:])
                    print "value_list",value_list


    return valid_options_dict     
    
def TestLdap():
    logger.setLevelDebug()

    ldap = LDAPapi()
    ret = ldap.conn.connect(bind=True)
    ldap.conn.close() 
    print "TEST ldap.conn.connect(bind=True)" , ret
    
    ret = ldap.conn.connect(bind=False)
    ldap.conn.close()
    print "TEST ldap.conn.connect(bind=False)", ret


    ret = ldap.LdapSearch()
    print "TEST ldap.LdapSearch ALL",ret
    
    ret = ldap.LdapSearch('(uid=avakian)', [])
    print "\r\n TEST ldap.LdapSearch ids = avakian",ret


    password = ldap.generate_password()
    print "\r\n TEST generate_password ",password 
    
    maxi = ldap.find_max_uidNumber()
    print "\r\n TEST find_max_uidNumber " , maxi

    data = {}
    data['last_name'] = "Drake"
    data['first_name']="Tim"
    data['givenName']= data['first_name']
    data['mail'] = "robin@arkham.fr"
    
    record={}
    record['hrn'] = 'senslab2.drake'
    record['last_name'] = "Drake"
    record['first_name']="Tim"
    record['mail'] = "robin@arkham.fr"
    
    datanight = {}
    datanight['last_name'] = "Grayson"
    datanight['first_name']="Dick"
    datanight['givenName']= datanight['first_name']
    datanight['mail'] = "nightwing@arkham.fr"
    
    
    record_night = {}
    record_night['hrn'] = 'senslab2.grayson'
    record_night['last_name'] = datanight['last_name']
    record_night['first_name'] = datanight['first_name']
    record_night['mail'] = datanight['mail']
    
    login = ldap.generate_login(data)
    print "\r\n Robin \tgenerate_login  ", ret 
    
    ret = ldap.LdapAddUser(data)
    print "\r\n Robin  \tLdapAddUser ", ret 

    req_ldap = '(uid=' + login + ')'
    ret = ldap.LdapSearch(req_ldap, [])
    print "\r\n Robin \tldap.LdapSearch ids = %s %s"%(login,ret )
    
    password = "Thridrobin"
    enc = ldap.encrypt_password(password)
    print "\r\n Robin \tencrypt_password ", enc
    
    ret = ldap.LdapModifyUser(record, {'userPassword':enc})
    print "\r\n Robin \tChange password LdapModifyUser ", ret 
    
    dn = 'uid=' + login + ',' + ldap.baseDN
    ret = ldap.LdapDelete(dn)
    print "\r\n Robin  \tLdapDelete ", ret 
    
    ret = ldap.LdapFindUser(record_night)
    print "\r\n Nightwing \tldap.LdapFindHrn %s : %s"%(record_night,ret)
    
    ret = ldap.LdapSearch('(uid=grayson)', [])
    print "\r\n Nightwing \tldap.LdapSearch ids = %s %s"%('grayson',ret )

    ret = ldap.LdapAddUser(datanight)
    print "\r\n Nightwing \tLdapAddUser ", ret 
    
    ret = ldap.LdapResetPassword(record_night)
    print "\r\n Nightwing  \tLdapResetPassword de %s : %s "%(record_night,ret)
    
    ret = ldap.LdapDeleteUser(record_night)
    print "\r\n Nightwing   \tLdapDeleteUser ", ret 
    
    
    record_avakian = {}
    record_avakian['last_name'] = 'avakian'
    record_avakian['first_name'] = 'sandrine'
    record_avakian['email'] = 'sandrine.avakian@inria.fr'
    pubkey = "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAwSUkJ+cr3xM47h8lFkIXJoJhg4wHakTaLJmgTXkzvUmQsQeFB2MjUZ6WAelMXj/EFz2+XkK+bcWNXwfbrLptJQ+XwGpPZlu9YV/kzO63ghVrAyEg0+p7Pn1TO9f1ZYg4R6JfP/3qwH1AsE+X3PNpIewsuEIKwd2wUCJDf5RXJTpl39GizcBFemrRqgs0bdqAN/vUT9YvtWn8fCYR5EfJHVXOK8P1KmnbuGZpk7ryz21pDMlgw13+8aYB+LPkxdv5zG54A5c6o9N3zOCblvRFWaNBqathS8y04cOYWPmyu+Q0Xccwi7vM3Ktm8RoJw+raQNwsmneJOm6KXKnjoOQeiQ== savakian@sfa2.grenoble.senslab.info"
    
    ret = ldap.LdapModifyUser(record_avakian, {'sshPublicKey':pubkey})
    print "\r\n Sandrine \tChange pubkey LdapModifyUser ", ret 
    
    password = "ReptileFight"
    enc = ldap.encrypt_password(password)
    print "\r\n sandrine \tencrypt_password ", enc
    
    ret = ldap.LdapModifyUser(record_avakian, {'userPassword':enc})
    print "\r\n sandrine \tChange password LdapModifyUser ", ret 
    return


def get_stuff(oar, uri):
    import httplib
    import json    
    headers = {}
    data = json.dumps({})   
  
    headers['X-REMOTE_IDENT'] = 'avakian' 
      
    headers['content-length'] = '0' #seems that it does not work if we don't add this
            

    conn = httplib.HTTPConnection(oar.oarserver['ip'],oar.oarserver['port'])
    conn.request("GET",uri,data , headers )
    resp = ( conn.getresponse()).read()
            #logger.debug("OARrestapi: \t  GETRequestToOARRestAPI  resp %s" %( resp))
    conn.close()
      

    js = json.loads(resp)
    return js
            


  
def TestOAR(job_id = None):
    
    if isinstance(job_id,list) and len(job_id) == 1:
       job_id = job_id[0]
        
    oar = OARrestapi()
    jobs = oar.parser.SendRequest("GET_reserved_nodes", username = 'avakian') 
    print "\r\n OAR GET_reserved_nodes ",jobs
    
   
    
    jobs = oar.parser.SendRequest("GET_jobs") 
    print "\r\n OAR GET_jobs ",jobs
    
 
    jobs = oar.parser.SendRequest("GET_jobs_id", job_id, 'avakian')
    print "\r\n OAR  GET_jobs_id ",jobs
    
    uri = '/oarapi/jobs/details.json?state=Running,Waiting,Launching&user=avakian'      
    raw_json = get_stuff(oar,uri)
    print "\r\nOAR ", uri, raw_json, "\r\n KKK \t",raw_json.keys()
    
    uri = '/oarapi/jobs/' + job_id +'.json'
    raw_json = get_stuff(oar,uri)  
    print "\r\n OAR  ",uri,raw_json, "\r\n KKK \t",raw_json.keys()
    
    uri = '/oarapi/jobs/' + job_id + '/resources.json'
    raw_json = get_stuff(oar,uri)
    print "\r\n OAR  ",uri, raw_json, "\r\n KKK \t",raw_json.keys()
    
    time_format = "%Y-%m-%d %H:%M:%S"
   
    server_timestamp,server_tz = oar.parser.SendRequest("GET_timezone")
    
    print "\r\n OAR  GetTimezone ",server_timestamp, server_tz
    print(datetime.fromtimestamp(int(server_timestamp)).strftime('%Y-%m-%d %H:%M:%S'))

    uri = '/oarapi/resources/full.json'
    raw_json = get_stuff(oar,uri)
    print "\r\n OAR  ",uri, raw_json, "\r\n KKK \t",raw_json.keys()
    
    uri = '/oarapi/jobs.json?user=avakian'      
    raw_json = get_stuff(oar,uri)
    print "\r\nOAR ", uri, raw_json, "\r\n KKK \t",raw_json.keys()
    return
    
def TestSlabDriver(job_id):
    if isinstance(job_id,list) and len(job_id) == 1:
       job_id = job_id[0]
    slabdriver = SlabDriver(Config())
    nodes = slabdriver.GetReservedNodes(username='avakian')
    print "\r\n \r\n" ,nodes
    
    l = slabdriver.GetSlices(slice_filter = '29', slice_filter_type = 'record_id_user')
    
    
    print "\r\n \r\nGetSlices" ,l
    
    persons = slabdriver.GetPersons()
    print "\r\n \r\n  GetPersons" ,persons
    #slabdriver.DeleteJobs(job_id,'senslab2.avakian_slice')
   
def RunAll():
    TestLdap()
    TestOAR()
    
   
supported_options = {
        'OAR' : TestOAR,
        'LDAP': TestLdap,
        'driver': TestSlabDriver,
        'all' : RunAll }
        
def main():
    opts = parse_options()
    for opt in opts:
        supported_options[opt](opts[opt])
        
    #TestLdap()
    #TestOAR()
    
if __name__ == "__main__":
    main()    