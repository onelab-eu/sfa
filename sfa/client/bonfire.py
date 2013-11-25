#tested with federica 18
#yum -y install python-pip
#pip install requests
import requests
import xml.etree.ElementTree as ET

# helping functions
# ########################################################## #

def create_fed4fire_exp(name, groups, description, walltime, slice_id, exp_owner):
    # create experiement with tag fed4fire
    xmldescription='<experiment xmlns="http://api.bonfire-project.eu/doc/schemas/occi"><name>' + name + '</name><groups>' + groups + '</groups><description>' + description + '</description><walltime>' + walltime + '</walltime><status>ready</status><fed4fire><slice_id>' + slice_id + '</slice_id><exp_owner>' + exp_owner + '<exp_owner></fed4fire></experiment>'
    postexp("https://api.integration.bonfire.grid5000.fr/experiments", xmldescription)

def postexp(url, xmldescription):
    headers = {'content-type': 'application/vnd.bonfire+xml'}
    r = requests.post(url, data=xmldescription, headers=headers, verify=False, auth=('nlebreto', 'GDRU_23tc$'))

def stop_vm(testbed, num_compute):
    # compute bonfire to stopped state
    url = "https://api.integration.bonfire.grid5000.fr/" + "locations/" + testbed + "/computes/" + num_compute
    xmldescription = '<compute xmlns="http://api.bonfire-project.eu/doc/schemas/occi"><state>stopped</state></compute>'
    headers = {'content-type': 'application/vnd.bonfire+xml'}
    requests.put(url, data=xmldescription, headers=headers, verify=False, auth=('nlebreto', 'GDRU_23tc$'))

def provisioning(num_experiment):
    # experiment bonfire to running status
    url = "https://api.integration.bonfire.grid5000.fr/experiments/" + num_experiment
    xmldescription = '<experiment xmlns="http://api.bonfire-project.eu/doc/schemas/occi"><status>running</status></experiment>'
    headers = {'content-type': 'application/vnd.bonfire+xml'}
    requests.put(url, data=xmldescription, headers=headers, verify=False, auth=('nlebreto', 'GDRU_23tc$'))

def callcurl(url):
    r = requests.get(url, verify=False, auth=('nlebreto', 'GDRU_23tc$'))
    if r.status_code == 200:
        return r.text

def buildpagehttp(part1, part2):
    res = []
    for page in locations:
        res.append(part1 + page  + "/" + part2)
    return res

def boucle(itemname, xmltree, hashrspec, name):
    for item in xmltree.findall(itemname):
        hashrspec[name.text][itemname] = item.text

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
                        "      <planetlab:initscript name=\"" + hashrspec[clef]["name"]  + "\"/>" +
                        "  </sliver_type>")
        for infohost in itemshost:
            bonfires.append("  <planetlab:attribute name=\"" + infohost + "\"value=\"" + hashrspec[clef][infohost]  + "\"/>")
        bonfires.append("</node>")

def remove_needless_txt(txt):
    txt=str(txt)
    txt=txt.replace("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n","\n")
    txt=txt.replace("<?xml version='1.0' encoding='UTF-8'?>\n","\n")
    return txt

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

# parameters
# ########################################################## #
locations = ["fr-inria", "be-ibbt", "uk-epcc"]
urlnetworks = buildpagehttp("https://api.integration.bonfire.grid5000.fr/locations/", "networks")
urlstorages = buildpagehttp("https://api.integration.bonfire.grid5000.fr/locations/", "storages")
urlcomputes = buildpagehttp("https://api.integration.bonfire.grid5000.fr/locations/", "computes")

# main code
# ########################################################## #

# list for all bonfire resources
def bonsources():
    bonfires = []
    bonfires.append("<RSpec>")
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
