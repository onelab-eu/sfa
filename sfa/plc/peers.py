from sfa.util.xrn import get_authority
from types import StringTypes

def get_peer(api, hrn):
    # Becaues of myplc federation,  we first need to determine if this
    # slice belongs to out local plc or a myplc peer. We will assume it
    # is a local site, unless we find out otherwise
    peer = None

    # get this slice's authority (site)
    slice_authority = get_authority(hrn)

    # get this site's authority (sfa root authority or sub authority)
    site_authority = get_authority(slice_authority).lower()
    # check if we are already peered with this site_authority, if so
    peers = api.driver.GetPeers( {}, ['peer_id', 'peername', 'shortname', 'hrn_root'])
    for peer_record in peers:
        names = [name.lower() for name in peer_record.values() if isinstance(name, StringTypes)]
        if site_authority in names:
            peer = peer_record['shortname']

    return peer


def get_sfa_peer(api, hrn):
    # return the authority for this hrn or None if we are the authority
    sfa_peer = None
    slice_authority = get_authority(hrn)
    site_authority = get_authority(slice_authority)

    if site_authority != api.hrn:
        sfa_peer = site_authority

    return sfa_peer

