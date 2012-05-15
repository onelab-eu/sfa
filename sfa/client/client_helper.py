import sys
def pg_users_arg(records):
    users = []  
    for record in records:
        if record['type'] != 'user': 
            continue
        user = {'urn': record['geni_urn'],
                'keys': record['keys']}
        users.append(user)
    return users    

def sfa_users_arg(records, slice_record):
    users = []
    print>>sys.stderr, " \r\n \r\n \t CLIENT_HELPER.PY sfa_users_arg slice_record %s \r\n records %s"%(slice_record,records)
    for record in records:
        if record['type'] != 'user': 
            continue
        user = {'urn': record['geni_urn'], 
                'keys': record['keys'],
                'email': record['email'], # needed for MyPLC
                'person_id': record['record_id'], 
                'hrn': record['hrn'],
                'type': record['type'],
                'authority' : record['authority'],
                'gid' : record['gid'],
                'first_name': record['first_name'], # needed for MyPLC
                'last_name': record['last_name'], # needed for MyPLC
                'slice_record': slice_record, # needed for legacy refresh peer
                'key_ids': record['key_ids'] # needed for legacy refresh peer
                }         
        users.append(user)   
        print>>sys.stderr, " \r\n \r\n \t CLIENT_HELPER.PY sfa_users_arg user %s",user
    return users        

def sfa_to_pg_users_arg(users):

    new_users = []
    fields = ['urn', 'keys']
    for user in users:
        new_user = dict([item for item in user.items() \
          if item[0] in fields])
        new_users.append(new_user)
    return new_users        
