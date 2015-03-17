#!/usr/bin/env python
# -*- coding:utf-8 -*-

import types

from sfa.storage.model import *
from sfa.storage.alchemy import *
from sfa.trust.gid import create_uuid
from sfa.trust.hierarchy import Hierarchy
from sfa.util.xrn import Xrn
from sfa.trust.certificate import Certificate, Keypair, convert_public_key

def fix_users():
    s=global_dbsession
    hierarchy = Hierarchy()
    users = s.query(RegRecord).filter_by(type="user")
    for record in users:
        record.gid = ""
        if not record.gid:
            uuid = create_uuid()
            pkey = Keypair(create=True)
            pub_key=getattr(record,'reg_keys',None)
            if len(pub_key) > 0:
                # use only first key in record
                if pub_key and isinstance(pub_key, types.ListType): pub_key = pub_key[0]
                pub_key = pub_key.key
                pkey = convert_public_key(pub_key)
            urn = Xrn (xrn=record.hrn, type='user').get_urn()
            email=getattr(record,'email',None)
            gid_object = hierarchy.create_gid(urn, uuid, pkey, email = email)
            gid = gid_object.save_to_string(save_parents=True)
            record.gid = gid
    s.commit()

if __name__ == '__main__':
    fix_users()
