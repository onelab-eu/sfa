###########################################################################
#    Copyright (C) 2012 by
#    <savakian@sfa2.grenoble.iotlab.info>
#
# Copyright: See COPYING file that comes with this distribution
#
###########################################################################
#LDAP import
from sfa.iotlab.LDAPapi import LDAPapi
import ldap.modlist as modlist

#logger sfa
from sfa.util.sfalogging import logger

#OAR imports
from datetime import datetime
from sfa.iotlab.OARrestapi import OARrestapi

#Test iotlabdriver
from sfa.iotlab.iotlabdriver import IotlabDriver
from sfa.iotlab.iotlabshell import IotlabShell
from sfa.util.config import Config

from sfa.generic import Generic
import os
import sys


def message_and_wait(message):
    print message
    raw_input("Press Enter to continue...")

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
        #-10 OAR -2 IotlabDriver
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

def TestLdap(uid = None):
    logger.setLevelDebug()

    ldap_server = LDAPapi()
    ret = ldap_server.conn.connect(bind=True)
    ldap_server.conn.close()
    print "TEST ldap_server.conn.connect(bind=True)" , ret

    ret = ldap_server.conn.connect(bind=False)
    ldap_server.conn.close()
    print "TEST ldap_server.conn.connect(bind=False)", ret

    message_and_wait("\r\n \tLdapSeach : Get all users")
    ret = ldap_server.LdapSearch()
    print "\r\n", ret

    message_and_wait("\r\n \tLdapSeach : Get user with uid avakian")
    ret = ldap_server.LdapSearch('(uid=avakian)', [])
    print "\r\n", ret

    message_and_wait("\r\n  generate ...")
    password = ldap_server.login_pwd.generate_password()
    print   "\r\n TEST  generate_password ", password

    data = {}
    data['last_name'] = "Drake"
    data['first_name'] = "Tim"
    data['givenName'] = data['first_name']
    data['mail'] = "robin@arkham.fr"

    record = {}
    record['hrn'] = 'iotlab.drake'
    record['last_name'] = "Drake"
    record['first_name'] = "Tim"
    record['mail'] = "robin@arkham.fr"

    login = ldap_server.LdapGenerateUniqueLogin(data)
    print "\r\n Robin \tgenerate_login  ", login

    message_and_wait("\r\n find_max_uidNumber")
    maxi = ldap_server.find_max_uidNumber()
    print maxi



    ret = ldap_server.LdapAddUser(data)
    print "\r\n Robin  \tLdapAddUser ", ret

    req_ldap = '(uid=' + login + ')'
    ret = ldap_server.LdapSearch(req_ldap, [])
    print "\r\n Robin \tldap_server.LdapSearch ids = %s %s" % (login, ret)

    message_and_wait("Password methods")
    password = "Thridrobin"
    enc = ldap_server.login_pwd.encrypt_password(password)
    print "\r\n Robin \tencrypt_password ", enc

    ret = ldap_server.LdapModifyUser(record, {'userPassword':enc})
    print "\r\n Robin \tChange password LdapModifyUser ", ret



    datanight = {}
    datanight['last_name'] = "Grayson"
    datanight['first_name'] = "Dick"
    datanight['givenName'] = datanight['first_name']
    datanight['mail'] = "nightwing@arkham.fr"


    record_night = {}
    record_night['hrn'] = 'iotlab.grayson'
    record_night['last_name'] = datanight['last_name']
    record_night['first_name'] = datanight['first_name']
    record_night['mail'] = datanight['mail']

    message_and_wait("\r\n LdapFindUser")
    ret = ldap_server.LdapFindUser(record_night)
    print "\r\n Nightwing \tldap_server.LdapFindUser %s : %s" % (record_night,
        ret)

    #ret = ldap_server.LdapSearch('(uid=grayson)', [])
    #print "\r\n Nightwing \tldap_server.LdapSearch ids = %s %s" %('grayson',ret )
    message_and_wait("Add user then delete user")
    ret = ldap_server.LdapAddUser(datanight)
    print "\r\n Nightwing \tLdapAddUser ", ret

    #ret = ldap_server.LdapResetPassword(record_night)
    #print "\r\n Nightwing  \tLdapResetPassword de %s : %s" % (record_night, ret)

    ret = ldap_server.LdapDeleteUser(record_night)
    print "\r\n Nightwing   \tLdapDeleteUser ", ret


    #record_myslice = {}
    #record_myslice['hrn']= 'iotlab.myslice'
    #record_myslice['last_name'] = 'myslice'
    #record_myslice['first_name'] = 'myslice'
    #record_myslice['mail'] = 'nturro@inria.fr'
    #pubkeymyslice = "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAuyRPwn8PZxjdhu+ciRuPyM0eVBn7XS7i3tym9F30UVhaCd09a/UEmGn7WJZdfsxV3hXqG1Wc766FEst97NuzHzELSuvy/rT96J0UHG4wae4pnzOLd6NwFdZh7pkPsgHMHxK9ALVE68Puu+EDSOB5bBZ9Q624wCIGxEpmuS/+X+dDBTKgG5Hi0WA1uKJwhLSbbXb38auh4FlYgXPsdpljTIJatt+zGL0Zsy6fdrsVRc5W8kr3/SmE4OMNyabKBNyxioSEuYhRSjoQAHnYoevEjZniP8IzscKK7qwelzGUfnJEzexikhsQamhAFti2ReiFfoHBRZxnSc49ioH7Kaci5w== root@rhoecos3.ipv6.lip6.fr"

    #pubkeytestuser = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDYS8tzufciTm6GdNUGHQc64OfTxFebMYUwh/Jl04IPTvjjr26uakbM0M2v33HxZ5Q7PnmPN9pB/w+a+f7a7J4cNs/tApOMg2hb6UrLaOrdnDMOs4KZlfElyDsF3Zx5QwxPYvzsKADAbDVoX4NF9PttuDLdm2l3nLSvm89jfla00GBg+K8grdOCHyYZVX/Wt7kxhXDK3AidQhKJgn+iD5GxvtWMBE+7S5kJGdRW1W10lSLBW3+VNsCrKJB2s8L55Xz/l2HNBScU7T0VcMQJrFxEXKzLPagZsMz0lfLzHESoGHIZ3Tz85DfECbTtMxLts/4KoAEc3EE+PYr2VDeAggDx testuser@myslice"




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
    resp = (conn.getresponse()).read()

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
    print "============USING OAR CLASS PARSING METHODS ================"

    message_and_wait("\r\nGET_reserved_nodes")
    nodes = oar.parser.SendRequest("GET_reserved_nodes", username = 'avakian')
    print "\r\n OAR GET_reserved_nodes ", nodes

    message_and_wait("GET_jobs")
    jobs = oar.parser.SendRequest("GET_jobs")
    print "\r\n OAR GET_jobs ", jobs

    message_and_wait( "\r\n GET_jobs_id")
    jobs = oar.parser.SendRequest("GET_jobs_id", job_id, 'avakian')
    print "\r\n OAR  GET_jobs_id ", jobs

    # Check that the OAR requests are valid

    print "============RAW JSON FROM OAR ================"
    message_and_wait("\r\n Get all the jobs in the state  Running,Waiting, \
        Launching of the user ")
    uri = '/oarapi/jobs/details.json?state=Running,Waiting,Launching&user=avakian'
    raw_json = get_stuff(oar, uri)
    print "\r\n OAR  uri %s \r\n \t raw_json %s \r\n raw_json_keys %s " %(uri,
        raw_json, raw_json.keys())


    message_and_wait("\r\nGet information on the job identified by its job_id")
    uri = '/oarapi/jobs/' + job_id +'.json'
    raw_json = get_stuff(oar, uri)
    print "\r\n OAR  uri %s \r\n \t raw_json %s \r\n raw_json_keys %s " %(uri,
        raw_json, raw_json.keys())


    message_and_wait(" \r\nGet all the job's resources, \
        job defined by its job id %s"%(job_id))
    uri = '/oarapi/jobs/' + job_id + '/resources.json'
    raw_json = get_stuff(oar, uri)
    print "\r\n OAR  uri %s \r\n \t raw_json %s \r\n raw_json_keys %s " %(uri,
        raw_json, raw_json.keys())


    message_and_wait("\r\n Get server's date and timezone")
    time_format = "%Y-%m-%d %H:%M:%S"
    server_timestamp, server_tz = oar.parser.SendRequest("GET_timezone")
    print "\r\n OAR  GetTimezone ", server_timestamp, server_tz
    print(datetime.fromtimestamp(int(server_timestamp)).strftime(
                                                time_format))

    message_and_wait("\r\n Get all the resources with details from OAR")
    uri = '/oarapi/resources/full.json'
    raw_json = get_stuff(oar, uri)
    print "\r\n OAR  uri %s \r\n \t raw_json %s \r\n raw_json_keys %s " %(uri,
        raw_json, raw_json.keys())

    message_and_wait("\r\n Get all the jobs scheduled by the user")
    uri = '/oarapi/jobs.json?user=avakian'
    raw_json = get_stuff(oar, uri)
    print "\r\n OAR  uri %s \r\n \t raw_json %s \r\n raw_json_keys %s " %(uri,
        raw_json, raw_json.keys())

    return



def TestIotlabshell(param = None):

    config = Config()
    shell = IotlabShell(config)

    message_and_wait("\r\n \r\n GetReservedNodes")
    nodes = shell.GetReservedNodes()
    print nodes

    message_and_wait("\r\n GetPersons")
    persons = shell.GetPersons()
    print "\r\n \r\n  GetPersons", persons


    message_and_wait("\r\n GetLeases for the login avakian")
    leases = shell.GetLeases(login='avakian')
    print  leases

    message_and_wait("\r\n GetLeases for slice iotlab.avakian_slice")
    leases = shell.GetLeases(lease_filter_dict=
                        {'slice_hrn':'iotlab.avakian_slice'})
    print leases

    message_and_wait("\r\n GetLeases t_from 1405070000 ")
    leases = shell.GetLeases(lease_filter_dict={'t_from':1405070000})
    print leases

def TestIotlabDriver(job_id = None):
    if job_id is None:
        job_id = 1

    if isinstance(job_id, list) and len(job_id) == 1:
        job_id = job_id[0]

    api = Generic.the_flavour().make_api(interface='registry')
    iotlabdriver = IotlabDriver(api)

    # Iotlabdriver methods
    slice_hrn = 'iotlab.avakian_slice'
    message_and_wait(("\r\n GetSlices slice_hrn %s "%(slice_hrn)))
    sl = iotlabdriver.GetSlices(
            slice_filter= slice_hrn, slice_filter_type='slice_hrn')
    print sl

    message_and_wait("\r\n GetSlices slice filter 20 (record_id_user) ")
    sl = iotlabdriver.GetSlices(slice_filter='20',
                                slice_filter_type='record_id_user')
    print sl

    message_and_wait("\r\n GetSlices :all slice")
    sl = iotlabdriver.GetSlices()
    print sl






def TestSQL(arg = None):
    from sfa.storage.model import make_record, RegSlice, RegRecord
    from sfa.storage.alchemy import global_dbsession


    from sqlalchemy.orm import joinedload

    slice_hrn = 'iotlab.avakian_slice'
    request =  global_dbsession.query(RegSlice).options(joinedload('reg_researchers'))
    solo_query_slice_list = request.filter_by(hrn=slice_hrn).first()

    print "\r\n \r\n ===========      solo_query_slice_list  RegSlice \
    joinedload('reg_researchers')   slice_hrn %s  first %s \r\n \t "\
    %(slice_hrn, solo_query_slice_list.__dict__)

    query_slice_list = request.all()
    print "\r\n \r\n ===========      query_slice_list RegSlice \
    joinedload('reg_researchers')   ALL  \r\n \t", \
    query_slice_list[0].__dict__

    return_slicerec_dictlist = []
    record = query_slice_list[0]
    print "\r\n \r\n ===========   \r\n \t", record

    tmp = record.__dict__
    print "\r\n \r\n ===========   \r\n \t", tmp
    tmp['reg_researchers'] = tmp['reg_researchers'][0].__dict__
    print "\r\n \r\n ===========   \r\n \t", tmp
        #del tmp['reg_researchers']['_sa_instance_state']
    return_slicerec_dictlist.append(tmp)

    print "\r\n \r\n ===========   \r\n \t", return_slicerec_dictlist

    all_records = global_dbsession.query(RegRecord).all()



def RunAll( arg ):
    TestLdap()
    TestOAR()
    TestIotlabDriver()
    TestSfi()


supported_options = {
        'OAR' : TestOAR,
        'LDAP': TestLdap,
        'driver': TestIotlabDriver,
        'shell': TestIotlabshell,
        'sql':TestSQL,
        'all' : RunAll, }

def main():
    opts = parse_options()
    print opts
    for opt in opts:
        supported_options[opt](opts[opt])


if __name__ == "__main__":
    main()