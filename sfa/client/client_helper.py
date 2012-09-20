
def pg_users_arg(records):
    users = []  
    for record in records:
        if record['type'] != 'user': 
            continue
        user = {'urn': record['urn'],
                'keys': record['keys']}
        users.append(user)
    return users    

def sfa_users_arg (records, slice_record):
    users = []
    for record in records:
        if record['type'] != 'user': 
            continue
        try:
            user = {'urn': record['urn'], #
# all right, so this is sooo totally wrong
#                    'keys': record['keys'],
#                    'email': record['email'], # needed for MyPLC
#                    'person_id': record['person_id'], # needed for MyPLC
#                    'first_name': record['first_name'], # needed for MyPLC
#                    'last_name': record['last_name'], # needed for MyPLC
#                    'slice_record': slice_record, # needed for legacy refresh peer
#                    'key_ids': record['key_ids'] # needed for legacy refresh peer
                    }
        except:
            # handle NITOS user args
            user = {'urn': record['urn'], 
                    'keys': record['keys'],
                    'email': record['email'], 
                    'user_id': record['user_id'], 
                    'slice_record': slice_record,
                    }
            
        users.append(user)

    return users

def sfa_to_pg_users_arg(users):

    new_users = []
    fields = ['urn', 'keys']
    for user in users:
        new_user = dict([item for item in user.items() \
          if item[0] in fields])
        new_users.append(new_user)
    return new_users        
