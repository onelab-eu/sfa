import os
import time
import re

from sfa.util.faults import *
from sfa.util.sfalogging import logger
from sfa.util.config import Config
from sfa.util.sfatime import utcparse
from sfa.util.callids import Callids
from sfa.util.version import version_core
from sfa.util.xrn import urn_to_hrn, hrn_to_urn, get_authority, Xrn
from sfa.util.plxrn import hrn_to_pl_slicename

from sfa.server.sfaapi import SfaApi
from sfa.server.registry import Registries
from sfa.rspecs.rspec_version import RSpecVersion
from sfa.rspecs.sfa_rspec import sfa_rspec_version
from sfa.rspecs.rspec_parser import parse_rspec

from sfa.managers.aggregate_manager import __get_registry_objects, ListSlices

from sfa.plc.slices import Slices


RSPEC_TMP_FILE_PREFIX = "/tmp/max_rspec"

# execute shell command and return both exit code and text output
def shell_execute(cmd, timeout):
    pipe = os.popen('{ ' + cmd + '; } 2>&1', 'r')
    pipe = os.popen(cmd + ' 2>&1', 'r')
    text = ''
    while timeout:
        line = pipe.read()
        text += line
        time.sleep(1)
        timeout = timeout-1
    code = pipe.close()
    if code is None: code = 0
    if text[-1:] == '\n': text = text[:-1]
    return code, text

"""
 call AM API client with command like in the following example:
 cd aggregate_client; java -classpath AggregateWS-client-api.jar:lib/* \
      net.geni.aggregate.client.examples.CreateSliceNetworkClient \
      ./repo https://geni:8443/axis2/services/AggregateGENI \
      ... params ...
"""

def call_am_apiclient(client_app, params, timeout):
    (client_path, am_url) = Config().get_max_aggrMgr_info()
    sys_cmd = "cd " + client_path + "; java -classpath AggregateWS-client-api.jar:lib/* net.geni.aggregate.client.examples." + client_app + " ./repo " + am_url + " " + ' '.join(params)
    ret = shell_execute(sys_cmd, timeout)
    logger.debug("shell_execute cmd: %s returns %s" % (sys_cmd, ret))
    return ret

# save request RSpec xml content to a tmp file
def save_rspec_to_file(rspec):
    path = RSPEC_TMP_FILE_PREFIX + "_" + time.strftime('%Y%m%dT%H:%M:%S', time.gmtime(time.time())) +".xml"
    file = open(path, "w")
    file.write(rspec)
    file.close()
    return path

# get stripped down slice id/name plc.maxpl.xislice1 --> maxpl_xislice1
def get_plc_slice_id(cred, xrn):
    (hrn, type) = urn_to_hrn(xrn)
    slice_id = hrn.find(':')
    sep = '.'
    if hrn.find(':') != -1:
        sep=':'
    elif hrn.find('+') != -1:
        sep='+'
    else:
        sep='.'
    slice_id = hrn.split(sep)[-2] + '_' + hrn.split(sep)[-1]
    return slice_id

# extract xml 
def get_xml_by_tag(text, tag):
    indx1 = text.find('<'+tag)
    indx2 = text.find('/'+tag+'>')
    xml = None
    if indx1!=-1 and indx2>indx1:
        xml = text[indx1:indx2+len(tag)+2]
    return xml

def prepare_slice(api, slice_xrn, creds, users):
    reg_objects = __get_registry_objects(slice_xrn, creds, users)
    (hrn, type) = urn_to_hrn(slice_xrn)
    slices = Slices(api)
    peer = slices.get_peer(hrn)
    sfa_peer = slices.get_sfa_peer(hrn)
    slice_record=None
    if users:
        slice_record = users[0].get('slice_record', {})
    registry = api.registries[api.hrn]
    credential = api.getCredential()
    # ensure site record exists
    site = slices.verify_site(hrn, slice_record, peer, sfa_peer)
    # ensure slice record exists
    slice = slices.verify_slice(hrn, slice_record, peer, sfa_peer)
    # ensure person records exists
    persons = slices.verify_persons(hrn, slice, users, peer, sfa_peer)

def parse_resources(text, slice_xrn):
    resources = []
    urn = hrn_to_urn(slice_xrn, 'sliver')
    plc_slice = re.search("Slice Status => ([^\n]+)", text)
    if plc_slice.group(1) != 'NONE':
        res = {}
        res['geni_urn'] = urn + '_plc_slice'
        res['geni_error'] = ''
        res['geni_status'] = 'unknown'
        if plc_slice.group(1) == 'CREATED':
            res['geni_status'] = 'ready'
        resources.append(res)
    vlans = re.findall("GRI => ([^\n]+)\n\t  Status => ([^\n]+)", text)
    for vlan in vlans:
        res = {}
        res['geni_error'] = ''
        res['geni_urn'] = urn + '_vlan_' + vlan[0]
        if vlan[1] == 'ACTIVE':
            res['geni_status'] = 'ready'
        elif vlan[1] == 'FAILED':
            res['geni_status'] = 'failed'
        else:
            res['geni_status'] = 'configuring'
        resources.append(res)
    return resources

def slice_status(api, slice_xrn, creds):
    urn = hrn_to_urn(slice_xrn, 'slice')
    result = {}
    top_level_status = 'unknown'
    slice_id = get_plc_slice_id(creds, urn)
    (ret, output) = call_am_apiclient("QuerySliceNetworkClient", [slice_id,], 5)
    # parse output into rspec XML
    if output.find("Unkown Rspec:") > 0:
        top_level_staus = 'failed'
        result['geni_resources'] = ''
    else:
        has_failure = 0
        all_active = 0
        if output.find("Status => FAILED") > 0:
            top_level_staus = 'failed'
        elif (    output.find("Status => ACCEPTED") > 0 or output.find("Status => PENDING") > 0
               or output.find("Status => INSETUP") > 0 or output.find("Status => INCREATE") > 0
             ):
            top_level_status = 'configuring'
        else:
            top_level_status = 'ready'
        result['geni_resources'] = parse_resources(output, slice_xrn)
    result['geni_urn'] = urn
    result['geni_status'] = top_level_status
    return result

def create_slice(api, xrn, cred, rspec, users):
    indx1 = rspec.find("<RSpec")
    indx2 = rspec.find("</RSpec>")
    if indx1 > -1 and indx2 > indx1:
        rspec = rspec[indx1+len("<RSpec type=\"SFA\">"):indx2-1]
    rspec_path = save_rspec_to_file(rspec)
    prepare_slice(api, xrn, cred, users)
    slice_id = get_plc_slice_id(cred, xrn)
    sys_cmd = "sed -i \"s/rspec id=\\\"[^\\\"]*/rspec id=\\\"" +slice_id+ "/g\" " + rspec_path + ";sed -i \"s/:rspec=[^:'<\\\" ]*/:rspec=" +slice_id+ "/g\" " + rspec_path
    ret = shell_execute(sys_cmd, 1)
    sys_cmd = "sed -i \"s/rspec id=\\\"[^\\\"]*/rspec id=\\\"" + rspec_path + "/g\""
    ret = shell_execute(sys_cmd, 1)
    (ret, output) = call_am_apiclient("CreateSliceNetworkClient", [rspec_path,], 3)
    # parse output ?
    rspec = "<RSpec type=\"SFA\"> Done! </RSpec>"
    return True

def delete_slice(api, xrn, cred):
    slice_id = get_plc_slice_id(cred, xrn)
    (ret, output) = call_am_apiclient("DeleteSliceNetworkClient", [slice_id,], 3)
    # parse output ?
    return 1


def get_rspec(api, cred, slice_urn):
    logger.debug("#### called max-get_rspec")
    #geni_slice_urn: urn:publicid:IDN+plc:maxpl+slice+xi_rspec_test1
    if slice_urn == None:
        (ret, output) = call_am_apiclient("GetResourceTopology", ['all', '\"\"'], 5)
    else:
        slice_id = get_plc_slice_id(cred, slice_urn)
        (ret, output) = call_am_apiclient("GetResourceTopology", ['all', slice_id,], 5)
    # parse output into rspec XML
    if output.find("No resouce found") > 0:
        rspec = "<RSpec type=\"SFA\"> <Fault>No resource found</Fault> </RSpec>"
    else:
        comp_rspec = get_xml_by_tag(output, 'computeResource')
        logger.debug("#### computeResource %s" % comp_rspec)
        topo_rspec = get_xml_by_tag(output, 'topology')
        logger.debug("#### topology %s" % topo_rspec)
        rspec = "<RSpec type=\"SFA\"> <network name=\"" + Config().get_interface_hrn() + "\">";
        if comp_rspec != None:
            rspec = rspec + get_xml_by_tag(output, 'computeResource')
        if topo_rspec != None:
            rspec = rspec + get_xml_by_tag(output, 'topology')
        rspec = rspec + "</network> </RSpec>"
    return (rspec)

def start_slice(api, xrn, cred):
    # service not supported
    return None

def stop_slice(api, xrn, cred):
    # service not supported
    return None

def reset_slices(api, xrn):
    # service not supported
    return None

"""
    GENI AM API Methods
"""

def GetVersion(api):
    xrn=Xrn(api.hrn)
    request_rspec_versions = [dict(sfa_rspec_version)]
    ad_rspec_versions = [dict(sfa_rspec_version)]
    #TODO: MAX-AM specific
    version_more = {'interface':'aggregate',
                    'testbed':'myplc',
                    'hrn':xrn.get_hrn(),
                    'request_rspec_versions': request_rspec_versions,
                    'ad_rspec_versions': ad_rspec_versions,
                    'default_ad_rspec': dict(sfa_rspec_version)
                    }
    return version_core(version_more)

def SliverStatus(api, slice_xrn, creds, call_id):
    if Callids().already_handled(call_id): return {}
    return slice_status(api, slice_xrn, creds)

def CreateSliver(api, slice_xrn, creds, rspec_string, users, call_id):
    if Callids().already_handled(call_id): return ""
    #TODO: create real CreateSliver response rspec
    ret = create_slice(api, slice_xrn, creds, rspec_string, users)
    if ret:
        return get_rspec(api, creds, slice_xrn)
    else:
        return "<?xml version=\"1.0\" ?> <RSpec type=\"SFA\"> Error! </RSpec>"

def DeleteSliver(api, xrn, creds, call_id):
    if Callids().already_handled(call_id): return ""
    return delete_slice(api, xrn, creds)

# no caching
def ListResources(api, creds, options,call_id):
    if Callids().already_handled(call_id): return ""
    # version_string = "rspec_%s" % (rspec_version.get_version_name())
    slice_urn = options.get('geni_slice_urn')
    return get_rspec(api, creds, slice_urn)

def fetch_context(slice_hrn, user_hrn, contexts):
    """
    Returns the request context required by sfatables. At some point, this mechanism should be changed
    to refer to "contexts", which is the information that sfatables is requesting. But for now, we just
    return the basic information needed in a dict.
    """
    base_context = {'sfa':{'user':{'hrn':user_hrn}}}
    return base_context
    api = SfaApi()
    create_slice(api, "plc.maxpl.test000", None, rspec_xml, None)

