#!/usr/bin/python
# -*- coding:utf-8 -*-
#yum -y install python-pip
#pip install requests
import requests
import xml.etree.ElementTree as ET
import subprocess
import time

# module for bonfire to connect with sfa (following the Rspec)
# inspired by the following documenation :
# https://svn.planet-lab.org/wiki/SfaDeveloperDummyTutorial#RunningSFAinDummyflavour

# 1) list all the resources  of bonfire from sfa's point of view
# python -c 'import bonfire; print bonfire.bonsources()'

# 2) retrieve the url, the name and the key that will currently use by sfa for a compute N°3656 located at fr-inria
# python -c 'import bonfire; print bonfire.rsa_user_bonfire("fr-inria", "3656")'

# 3) create a new user and slice for sfa wrap
# python -c 'import bonfire; print bonfire.new_user_slice()'

# 4) changing the status to running status for the experiment 2911
# python -c 'import bonfire; print bonfire.provisioning("2911")'

# 5) stop virtual machine n°3756  at fr-inira testbed
# python -c 'import bonfire; print bonfire.stop_vm("fr-inria", "3756")'

# 6) allocation : create an experiment bonfire with slice information
# python -c 'import bonfire; print bonfire.allocate("nlebreto", "nlebreto", "tdes", "125", "topdomain.dummy.nicolasi", "https://api.integration.bonfire.grid5000.fr/experiments")'

# 7) remove slice or key 
# python -c 'import bonfire; print bonfire.remove_slice("topdomain.dummy.alice_slice")'

# 8) attach slice to a user (did not work)
# python -c 'import bonfire; print bonfire.create_slice_attach_user("topdomain.dummy.alice")'

# 9) verify bonfire authentication 
# # python -c 'import bonfire; print bonfire.callcurl("https://api.bonfire-project.eu/")'

# ########################################################## #
# ########################################################## #

# pseudo authentication for bonfire
def bonfire_authenticate():
    h = {}
    h["user"]      = "nlebreto"
    h["user_pass"] = "GDRU_23tc$"
    h["location"]  = "https://api.integration.bonfire.grid5000.fr"
    return h  

# create a slice and attach a specific user to it
def create_slice_attach_user(user_slice):
    call = "sfa.py add -x {0}_slice -t slice -r {0}@dummy.net".format(user_slice)
    callcreateslice =  subprocess.Popen(call, shell=True)

# remove slice or key
def remove_slice(name):
    cmdremove    = "sfaadmin.py reg remove {0}".format(name)
    removeaction = subprocess.Popen(cmdremove, shell=True)

# show specific credential of a slice    
def show_slice_credential(slice_name):
    path = "/root/.sfi/{0}.slice.cred".format(slice_name)
    tree = ET.parse(path)
    root = tree.getroot()
    hash = {}
    hash["slice_native"] = root.findall(".//signatures//{http://www.w3.org/2000/09/xmldsig#}Signature//{http://www.w3.org/2000/09/xmldsig#}KeyInfo//{http://www.w3.org/2000/09/xmldsig#}X509Data//{http://www.w3.org/2000/09/xmldsig#}X509SubjectName")[0].text
    for target in root.findall('credential'):
        hash["slice_user_urn"] = target.find('owner_urn').text
        hash["slice_urn"] = target.find('target_urn').text
        hash["serial"] = target.find('serial').text
    return hash

# create a bonfire experiment from a sfa point of view
def allocate(user_name, groups, description, walltime, slice_name):
    hash ={}
    hash = show_slice_credential(slice_name)
    create_fed4fire_exp(user_name, groups, description, walltime, hash["slice_urn"], hash["slice_user_urn"], hash["slice_native"])
    


# retrieve the url, the name and the key that will currently use by sfa
def rsa_user_bonfire(testbed, num_compute):
    url = "https://api.integration.bonfire.grid5000.fr/" + "locations/" + testbed + "/computes/" + num_compute
    pagebonfirecompute = callcurl(url)
    xmlreduit = ET.fromstring(pagebonfirecompute)
    hash = {}
    hash["url"] = url
    for name in xmlreduit:
        if name.tag == "{http://api.bonfire-project.eu/doc/schemas/occi}groups":
           hash["name"] = name.text
        for context in name:
            if context.tag == "{http://api.bonfire-project.eu/doc/schemas/occi}authorized_keys":
               hash["keys"] = context.text
    return hash 

# create a new user and slice for sfa wrap
def new_user_slice():
    n = rsa_user_bonfire("fr-inria", "3656")
    #url = n["url"] + "." + n["name"]
    # fix to do add -k id_rsa.pub (pb key convert)
    url = "topdomain.dummy." + n["name"]
    txtcreateuser = "sfaadmin.py reg register -x {0} -t user -e {1}@dummy.net".format(url, n["name"])
    createusersfa = subprocess.Popen(txtcreateuser, shell=True)
    #slice = n["url"] + "." + n["name"] + "_" + n["name"]
    slice = "topdomain.dummy." + n["name"] + "_slice"
    txtslice = "sfaadmin.py reg register -x {0} -t slice -r {1}".format(slice, url)
    createslice = subprocess.Popen(txtslice, shell=True)

# create a experiment bonfire with the slice urn and the experiment owner 
def create_fed4fire_exp(name, groups, description, walltime, slice_urn, slice_user_urn, slice_native, url_experiment_bonfire):
    xmldescription='<experiment xmlns="http://api.bonfire-project.eu/doc/schemas/occi"><name>' + name +'</name><groups>' + groups + '</groups><description>' + description + '</description><walltime>' + walltime + '</walltime><status>ready</status><slice_urn>' + slice_urn + '</slice_urn><slice_usr_urn>' + slice_user_urn + '<slice_usr_urn><slice_native>' + slice_native + '</slice_native></experiment>'
    postexp(url_experiment_bonfire, xmldescription)

# simple post method for request
def postexp(url, xmldescription):
    headers = {'content-type': 'application/vnd.bonfire+xml'}
    h = bonfire_authenticate()
    r = requests.post(url, data=xmldescription, headers=headers, verify=False, auth=(h["user"], h["user_pass"]))

# stop a virtual machine for bonfire 
# changing the state to stopped state
def stop_vm(testbed, num_compute):
    url = "https://api.integration.bonfire.grid5000.fr/" + "locations/" + testbed + "/computes/" + num_compute
    xmldescription = '<compute xmlns="http://api.bonfire-project.eu/doc/schemas/occi"><state>stopped</state></compute>'
    headers = {'content-type': 'application/vnd.bonfire+xml'}
    h = bonfire_authenticate()
    r = requests.post(url, data=xmldescription, headers=headers, verify=False, auth=(h["user"], h["user_pass"]))

# provisioning : set a bonfire's experiment to running  
# changing the status to running status
def provisioning(num_experiment):
    url = "https://api.integration.bonfire.grid5000.fr/experiments/" + num_experiment
    xmldescription = '<experiment xmlns="http://api.bonfire-project.eu/doc/schemas/occi"><status>running</status></experiment>'
    headers = {'content-type': 'application/vnd.bonfire+xml'}
    h = bonfire_authenticate()
    r = requests.post(url, data=xmldescription, headers=headers, verify=False, auth=(h["user"], h["user_pass"]))

# retrieving the url, the name and the keys for a specific compute 
def rsa_user_bonfire(testbed, num_compute):
    url = "https://api.integration.bonfire.grid5000.fr/" + "locations/" + testbed + "/computes/" + num_compute
    pagebonfirecompute = callcurl(url)
    xmlreduit = ET.fromstring(pagebonfirecompute)
    hash = {}
    hash["url"] = url
    for name in xmlreduit:
        if name.tag == "{http://api.bonfire-project.eu/doc/schemas/occi}groups":
           hash["name"] = name.text
        for context in name:
            if context.tag == "{http://api.bonfire-project.eu/doc/schemas/occi}authorized_keys":
               hash["keys"] = context.text
    return hash 

# do a curl request  
def callcurl(url):
    h = bonfire_authenticate()
    r = requests.get(url, verify=False, auth=(h["user"], h["user_pass"]))
    if r.status_code == 401:
        return "error 401, you need to be register to the portal f4f"
    if r.status_code == 200:
        return r.text
        
# create the url page 
def buildpagehttp(part1, part2, locations):
    res = []
    for page in locations:
        res.append(part1 + page  + "/" + part2)
    return res

def boucle(itemname, xmltree, hashrspec, name):
    for item in xmltree.findall(itemname):
        hashrspec[name.text][itemname] = item.text
        
# method to list all information from testbeds
def jfedfeat(bonfires, pageurl):
    pageforstatus = callcurl(pageurl)
    xmlreduit = ET.fromstring(pageforstatus)
    hashrspec = {}
    itemshost = ["DISK_USAGE", "MEM_USAGE", "CPU_USAGE", "MAX_DISK", "MAX_MEM",  "MAX_CPU",
                 "FREE_DISK",  "FREE_MEM",  "FREE_CPU", "FREE_MEM",  "FREE_CPU", "USED_DISK",
                 "USED_MEM",   "USED_CPU",  "RUNNING_VMS"
                ]
    # retrieve info for xml tree
    for host in xmlreduit.findall('HOST'):
        for name in host.findall('NAME'):
            hashrspec[name.text] = {"name" : name.text}
            for hostshare in host.findall('HOST_SHARE'):
                for itemshostname in itemshost:
                    boucle(itemshostname, hostshare, hashrspec, name)

 # jfed feature
    for clef in hashrspec:
        bonfires.append("<node component_manager_id=\"urn:publicid:IDN+topdomain+authority+cm" +
                        " component_id=\"urn:publicid:IDN+topdomain:" + hashrspec[clef]["name"] +
                        "\" component_name=" + hashrspec[clef]["name"] + "exclusive=\"false\">" +
                        "  <location country=\"unknown\" longitude=\"123456\" latitude=\"654321\"/>" +
                        "  <interface component_id=\"urn:publicid:IDN+ple+interface+node14312:eth0\"/>" +
                        "  <available now=\"true\"/>" +
                        "  <sliver_type name=\"" + hashrspec[clef]["name"] + "\">" +
                        "      <bonfire:initscript name=\"" + hashrspec[clef]["name"]  + "\"/>" +
                        "  </sliver_type>")
        for infohost in itemshost:
            bonfires.append("  <bonfire:attribute name=\"" + infohost + "\"value=\"" + hashrspec[clef][infohost]  + "\"/>")
        bonfires.append("</node>")

# remove the useless xml tag version 
def remove_needless_txt(txt):
    txt=str(txt)
    txt=txt.replace("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n","\n")
    txt=txt.replace("<?xml version='1.0' encoding='UTF-8'?>\n","\n")
    return txt

# list all bonfire resources following the sfa specification
def bonsources():
	# parameters
    locations = ["fr-inria", "be-ibbt", "uk-epcc"]
    urlnetworks = buildpagehttp("https://api.integration.bonfire.grid5000.fr/locations/", "networks", locations)
    urlstorages = buildpagehttp("https://api.integration.bonfire.grid5000.fr/locations/", "storages", locations)
    urlcomputes = buildpagehttp("https://api.integration.bonfire.grid5000.fr/locations/", "computes", locations)
    # main code
    bonfires = []
    generatedtime =  time.strftime("%FT%T%Z")
    sfabegin = "<RSpec type=\"SFA\" generated=" + generatedtime + "\">"
    bonfires.append("<?xml version=\"1.0\"?>")
    bonfires.append(sfabegin)
    bonfires.append("<managed_experiments>")
    manag_exp =  remove_needless_txt(callcurl("https://api.bonfire-project.eu/managed_experiments"))
    bonfires.append(manag_exp)
    bonfires.append("</managed_experiments><sites><machines>")
    jfedfeat(bonfires, "http://frontend.bonfire.grid5000.fr/one-status.xml")
    jfedfeat(bonfires, "http://bonfire.epcc.ed.ac.uk/one-status.xml")
    jfedfeat(bonfires, "http://bonfire.psnc.pl/one-status.xml")
    jfedfeat(bonfires, "http://nebulosus.rus.uni-stuttgart.de/one-status.xml")
    bonfires.append("</machines><networks>")
    for xmlnetworks in urlnetworks:
        bonfires.append(remove_needless_txt(callcurl(xmlnetworks)))
    bonfires.append("</networks><storages>")
    for xmlstorages in urlstorages:
        bonfires.append(remove_needless_txt(callcurl(xmlstorages)))
    bonfires.append("</storages><instance_types><computes>")
    for xmlcomputes in urlcomputes:
        bonfires.append(remove_needless_txt(callcurl(xmlcomputes)))
    bonfires.append("</computes></instance_types></sites><experiments>")
    exp = callcurl("https://api.integration.bonfire.grid5000.fr/experiments")
    rexp = remove_needless_txt(exp)
    bonfires.append(rexp)
    bonfires.append("</experiments><reservations>")
    reserv = callcurl("https://api.integration.bonfire.grid5000.fr/locations/fr-inria/reservations")
    rreserv = remove_needless_txt(reserv)
    bonfires.append(rreserv)
    bonfires.append("</reservations>")
    bonfires.append("</RSpec>")
    bonfires = "\n".join(bonfires)
    bonfires = bonfires.replace("\n\n","")
    return bonfires
