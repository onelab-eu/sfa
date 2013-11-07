#tested with federica 18
#yum -y install python-pip
#pip install requests
import requests
import xml.etree.ElementTree as ET

# helping functions
# ########################################################## #
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
    txt=txt.replace("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n","\n")
    txt=txt.replace("<?xml version='1.0' encoding='UTF-8'?>\n","\n")
    return txt

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
#   jfedfeat(bonfires, "http://bonfire.epcc.ed.ac.uk/logs/one-status.xml")
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
