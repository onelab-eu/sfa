###########################################################################
#    Copyright (C) 2012 by                                       
#    <savakian@sfa2.grenoble.senslab.info>                                                             
#
# Copyright: See COPYING file that comes with this distribution
#
###########################################################################
#LDAP import 
from sfa.senslab.LDAPapi import LDAPapi
import ldap.modlist as modlist


#logger sfa
from sfa.util.sfalogging import logger

#OAR imports
from datetime import datetime
from sfa.senslab.OARrestapi import OARrestapi

#Test slabdriver
from sfa.senslab.slabdriver import SlabDriver
from sfa.util.config import Config


import os
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
                    print "value_list", value_list


    return valid_options_dict     
    
def TestLdap(job_id = None):
    logger.setLevelDebug()

    ldap_server = LDAPapi()
    ret = ldap_server.conn.connect(bind=True)
    ldap_server.conn.close() 
    print "TEST ldap_server.conn.connect(bind=True)" , ret
    
    ret = ldap_server.conn.connect(bind=False)
    ldap_server.conn.close()
    print "TEST ldap_server.conn.connect(bind=False)", ret


    ret = ldap_server.LdapSearch()
    print "TEST ldap_server.LdapSearch ALL", ret
    
    ret = ldap_server.LdapSearch('(uid=avakian)', [])
    print "\r\n TEST ldap_server.LdapSearch ids = avakian", ret


    password = ldap_server.generate_password()
    print "\r\n TEST generate_password ", password 
    
    maxi = ldap_server.find_max_uidNumber()
    print "\r\n TEST find_max_uidNumber " , maxi

    data = {}
    data['last_name'] = "Drake"
    data['first_name'] = "Tim"
    data['givenName'] = data['first_name']
    data['mail'] = "robin@arkham.fr"
    
    record = {}
    record['hrn'] = 'senslab.drake'
    record['last_name'] = "Drake"
    record['first_name'] = "Tim"
    record['mail'] = "robin@arkham.fr"
    
    
    login = ldap_server.generate_login(data)
    print "\r\n Robin \tgenerate_login  ", ret, login
    
    ret = ldap_server.LdapAddUser(data)
    print "\r\n Robin  \tLdapAddUser ", ret

    req_ldap = '(uid=' + login + ')'
    ret = ldap_server.LdapSearch(req_ldap, [])
    print "\r\n Robin \tldap_server.LdapSearch ids = %s %s" % (login, ret)
    
    password = "Thridrobin"
    enc = ldap_server.encrypt_password(password)
    print "\r\n Robin \tencrypt_password ", enc
    
    ret = ldap_server.LdapModifyUser(record, {'userPassword':enc})
    print "\r\n Robin \tChange password LdapModifyUser ", ret
    
    #dn = 'uid=' + login + ',' + ldap_server.baseDN
    #ret = ldap_server.LdapDelete(dn)
    #print "\r\n Robin  \tLdapDelete ", ret
    
    datanight = {}
    datanight['last_name'] = "Grayson"
    datanight['first_name'] = "Dick"
    datanight['givenName'] = datanight['first_name']
    datanight['mail'] = "nightwing@arkham.fr"
    
    
    record_night = {}
    record_night['hrn'] = 'senslab.grayson'
    record_night['last_name'] = datanight['last_name']
    record_night['first_name'] = datanight['first_name']
    record_night['mail'] = datanight['mail']
    
    ret = ldap_server.LdapFindUser(record_night)
    print "\r\n Nightwing \tldap_server.LdapFindUser %s : %s" % (record_night, ret)
    
    #ret = ldap_server.LdapSearch('(uid=grayson)', [])
    #print "\r\n Nightwing \tldap_server.LdapSearch ids = %s %s" %('grayson',ret )

    #ret = ldap_server.LdapAddUser(datanight)
    #print "\r\n Nightwing \tLdapAddUser ", ret 
    
    #ret = ldap_server.LdapResetPassword(record_night)
    #print "\r\n Nightwing  \tLdapResetPassword de %s : %s" % (record_night, ret)
    
    ret = ldap_server.LdapDeleteUser(record_night)
    print "\r\n Nightwing   \tLdapDeleteUser ", ret 
    
    
    #record_avakian = {}
    #record_avakian['hrn']= 'senslab.avakian'
    #record_avakian['last_name'] = 'avakian'
    #record_avakian['first_name'] = 'sandrine'
    #record_avakian['mail'] = 'sandrine.avakian@inria.fr'
    #pubkey = "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAwSUkJ+cr3xM47h8lFkIXJoJhg4wHakTaLJmgTXkzvUmQsQeFB2MjUZ6WAelMXj/EFz2+XkK+bcWNXwfbrLptJQ+XwGpPZlu9YV/kzO63ghVrAyEg0+p7Pn1TO9f1ZYg4R6JfP/3qwH1AsE+X3PNpIewsuEIKwd2wUCJDf5RXJTpl39GizcBFemrRqgs0bdqAN/vUT9YvtWn8fCYR5EfJHVXOK8P1KmnbuGZpk7ryz21pDMlgw13+8aYB+LPkxdv5zG54A5c6o9N3zOCblvRFWaNBqathS8y04cOYWPmyu+Q0Xccwi7vM3Ktm8RoJw+raQNwsmneJOm6KXKnjoOQeiQ== savakian@sfa2.grenoble.senslab.info"
    #ret = ldap_server.LdapModifyUser(record_night, {'sshPublicKey':pubkey})
    #print "\r\n Sandrine \tChange pubkey LdapModifyUser ", ret 
    
    #record_myslice = {}
    #record_myslice['hrn']= 'senslab.myslice'
    #record_myslice['last_name'] = 'myslice'
    #record_myslice['first_name'] = 'myslice'
    #record_myslice['mail'] = 'nturro@inria.fr'
    #pubkeymyslice = "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAuyRPwn8PZxjdhu+ciRuPyM0eVBn7XS7i3tym9F30UVhaCd09a/UEmGn7WJZdfsxV3hXqG1Wc766FEst97NuzHzELSuvy/rT96J0UHG4wae4pnzOLd6NwFdZh7pkPsgHMHxK9ALVE68Puu+EDSOB5bBZ9Q624wCIGxEpmuS/+X+dDBTKgG5Hi0WA1uKJwhLSbbXb38auh4FlYgXPsdpljTIJatt+zGL0Zsy6fdrsVRc5W8kr3/SmE4OMNyabKBNyxioSEuYhRSjoQAHnYoevEjZniP8IzscKK7qwelzGUfnJEzexikhsQamhAFti2ReiFfoHBRZxnSc49ioH7Kaci5w== root@rhoecos3.ipv6.lip6.fr"
    
    #pubkeytestuser = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDYS8tzufciTm6GdNUGHQc64OfTxFebMYUwh/Jl04IPTvjjr26uakbM0M2v33HxZ5Q7PnmPN9pB/w+a+f7a7J4cNs/tApOMg2hb6UrLaOrdnDMOs4KZlfElyDsF3Zx5QwxPYvzsKADAbDVoX4NF9PttuDLdm2l3nLSvm89jfla00GBg+K8grdOCHyYZVX/Wt7kxhXDK3AidQhKJgn+iD5GxvtWMBE+7S5kJGdRW1W10lSLBW3+VNsCrKJB2s8L55Xz/l2HNBScU7T0VcMQJrFxEXKzLPagZsMz0lfLzHESoGHIZ3Tz85DfECbTtMxLts/4KoAEc3EE+PYr2VDeAggDx testuser@myslice"
    

    
    #password = "ReptileFight"
    #enc = ldap_server.encrypt_password(password)
    #print "\r\n sandrine \tencrypt_password ", enc
    
    #ret = ldap_server.LdapModifyUser(record_avakian, {'userPassword':enc})
    #print "\r\n sandrine \tChange password LdapModifyUser ", ret 
    return


def get_stuff(oar, uri):
    import httplib
    import json    
    headers = {}
    data = json.dumps({})   
  
    headers['X-REMOTE_IDENT'] = 'avakian' 
      
    headers['content-length'] = '0' #seems that it does not work if we don't add this
            

    conn = httplib.HTTPConnection(oar.oarserver['ip'], oar.oarserver['port'])
    conn.request("GET", uri, data , headers )
    resp = ( conn.getresponse()).read()

    conn.close()
      

    js = json.loads(resp)
    return js
            


  
def TestOAR(job_id = None):
    print "JOB_ID",  job_id    
    if isinstance(job_id, list) :
        if len(job_id) >= 1:
            job_id = job_id[0]
        else:
            job_id = '1'
    else:
        job_id = '1'    
    print "JOB_ID",  job_id    
    oar = OARrestapi()
    jobs = oar.parser.SendRequest("GET_reserved_nodes", username = 'avakian') 
    print "\r\n OAR GET_reserved_nodes ", jobs
    
    
    jobs = oar.parser.SendRequest("GET_jobs") 
    print "\r\n OAR GET_jobs ", jobs
    
 
    jobs = oar.parser.SendRequest("GET_jobs_id", job_id, 'avakian')
    print "\r\n OAR  GET_jobs_id ", jobs
    
    uri = '/oarapi/jobs/details.json?state=Running,Waiting,Launching&user=avakian'      
    raw_json = get_stuff(oar, uri)
    print "\r\nOAR ", uri, raw_json, "\r\n KKK \t", raw_json.keys()
    
    uri = '/oarapi/jobs/' + job_id +'.json'
    raw_json = get_stuff(oar, uri)  
    print "\r\n OAR  ", uri, raw_json, "\r\n KKK \t", raw_json.keys()
    
    uri = '/oarapi/jobs/' + job_id + '/resources.json'
    raw_json = get_stuff(oar, uri)
    print "\r\n OAR  ", uri, raw_json, "\r\n KKK \t", raw_json.keys()
    
    time_format = "%Y-%m-%d %H:%M:%S"
   
    server_timestamp, server_tz = oar.parser.SendRequest("GET_timezone")
    
    print "\r\n OAR  GetTimezone ", server_timestamp, server_tz
    print(datetime.fromtimestamp(int(server_timestamp)).strftime('%Y-%m-%d %H:%M:%S'))

    uri = '/oarapi/resources/full.json'
    raw_json = get_stuff(oar, uri)
    print "\r\n OAR  ", uri, raw_json, "\r\n KKK \t", raw_json.keys()
    
    uri = '/oarapi/jobs.json?user=avakian'      
    raw_json = get_stuff(oar, uri)
    print "\r\nOAR ", uri, raw_json, "\r\n KKK \t", raw_json.keys()
    return
    
    
  
def TestSlabDriver(job_id = None):
    if job_id is None:
        job_id = 1
        
    if isinstance(job_id, list) and len(job_id) == 1:
        job_id = job_id[0]
    slabdriver = SlabDriver(Config())
    
    #nodes = slabdriver.slab_api.GetReservedNodes()
    #print " \r\n \r\n GetReservedNodes", nodes
    
    #sl = slabdriver.slab_api.GetSlices(slice_filter='senslab.avakian_slice', slice_filter_type='slice_hrn') 
    #print "\r\n \r\nGetSlices", sl[0]
    
    #sl = slabdriver.slab_api.GetSlices(slice_filter='20', slice_filter_type='record_id_user')  
    #print "\r\n \r\nGetSlices", sl
    
    #sl = slabdriver.slab_api.GetSlices()  
    #print "\r\n \r\nGetSlices", sl
    
    persons = slabdriver.slab_api.GetPersons()
    print "\r\n \r\n  GetPersons", persons
    
    leases = slabdriver.slab_api.GetLeases(login='avakian')
    print "\r\n \r\n  GetLeases", leases


      
def  TestSfi(filename = None):

    if filename is None:
        filename = "/home/savakian/flab-sfa/test_rspec/my_lyon_nodes.rspec"
    print " =================    SFI.PY RESOURCES            =============", \
    os.system("sfi.py list senslab")
    
    print  os.system("sfi.py resources")

    print os.system("sfi.py resources -r slab")

    print os.system("sfi.py resources -l all")
    
    
    print "================ SFI.PY RESOURCES -R SLAB -L ALL ============\r\n", \
    os.system("sfi.py resources -r slab -l all")
     
    print "================ WRITING  sfi.py resources -l all ===========\r\n", \
    filename
    
    filename = filename.split(".")[0]+"_out.rspec"
    rspecfile = open(filename,"w")
    r = os.popen("sfi.py resources -l all") 
    for i in r.readlines():
        rspecfile.write(i)
    rspecfile.close()
    
    print " =================    SFI.PY SHOW SLICE   ============= \r\n", \
    os.system("sfi.py resources senslab.avakian_slice")
    
    print  " =================    SFI.PY SHOW USER   =============\r\n", \
    os.system("sfi.py show senslab.avakian_slice")

    print " =================    SFI.PY SHOW NODE   =============\r\n", \
    os.system("sfi.py show senslab.avakian")

    print " =================    SFI.PY SLICES       =============\r\n", \
    os.system("sfi.py show senslab.node6.devlille.senslab.info")

    print " =================    SFI.PY LIST SLICE   =============\r\n", \
    os.system("sfi.py slices")

    print " =================    SFI.PY STATUS SLICE   =============\r\n", \
    os.system("sfi.py status senslab.avakian_slice")
    
    print " =================    SFI.PY DELETE SLICE   =============\r\n", \
    os.system("sfi.py delete senslab.avakian_slice")
    
    print " =================    SFI.PY CREATE SLICE   =============\r\n", \
    os.system("sfi.py create senslab.avakian_slice \
     /home/savakian/flab-sfa/test_rspec/my_lyon_nodes.rspec")
      
def TestSQL(arg = None):
    from sfa.storage.model import make_record, RegSlice, RegRecord
    from sfa.storage.alchemy import dbsession
    from sqlalchemy.orm.collections import InstrumentedList 
    
    from sqlalchemy.orm import joinedload 
    
    #solo_query_slice_list = dbsession.query(RegSlice).options(joinedload('reg_researchers')).filter_by(hrn='senslab.avakian_slice').first()
    #print "\r\n \r\n ===========      query_slice_list  RegSlice \
    #joinedload('reg_researchers')   senslab.avakian  first \r\n \t ", \
    #solo_query_slice_list.__dict__
      
    #query_slice_list = dbsession.query(RegSlice).options(joinedload('reg_researchers')).all()             
    #print "\r\n \r\n ===========      query_slice_list RegSlice \
    #joinedload('reg_researchers')   ALL  \r\n \t", \
    #query_slice_list[0].__dict__ 
    
    #return_slicerec_dictlist = []
    #record = query_slice_list[0]
    #print "\r\n \r\n ===========   \r\n \t", record 
    
    #tmp = record.__dict__
    #print "\r\n \r\n ===========   \r\n \t", tmp 
    #tmp['reg_researchers'] = tmp['reg_researchers'][0].__dict__
    #print "\r\n \r\n ===========   \r\n \t", tmp 
        ##del tmp['reg_researchers']['_sa_instance_state']
    #return_slicerec_dictlist.append(tmp)
        
    #print "\r\n \r\n ===========   \r\n \t", return_slicerec_dictlist
    
    all_records = dbsession.query(RegRecord).all()
      
        #create hash by (type,hrn) 
        #used  to know if a given record is already known to SFA 
       
    records_by_type_hrn = \
            dict ( [ ( (record.type,record.hrn) , record ) for record in all_records ] )
    for (rec_type, rec) in records_by_type_hrn :
        if rec_type == 'user':
            print>>sys.stderr,"\r\n SLABIMPORT \t keys %s rec %s \r\n" %(rec_type, rec )
            
    users_rec_by_email = \
            dict ( [ (record.email, record) for record in all_records if record.type == 'user' ] )
    
    
def RunAll( arg ):
    TestLdap()
    TestOAR()
    TestSlabDriver()
    TestSfi()
    
   
supported_options = {
        'OAR' : TestOAR,
        'LDAP': TestLdap,
        'driver': TestSlabDriver,
        'sfi':TestSfi,
        'sql':TestSQL,
        'all' : RunAll }
        
def main():
    opts = parse_options()
    print opts
    for opt in opts:
        supported_options[opt](opts[opt])

    
if __name__ == "__main__":
    main()    