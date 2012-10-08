###
#
# Thierry - 2012 sept 21
#
# it seems terribly wrong that the client should decide to use PG- or PL- related code
# esp. in a context where we're trying to have more and more kinds of testbeds involved
#
# also, the 'users' filed that CreateSliver is expecting (the key point here is to get this right)
# is specified to have at least a urn and a list of keys, both of these being supported natively
# in the sfa db
# So long story short, it seems to me that we should have a common code that fills in 'urn' and 'keys'
# and then code that tentatively tries to add as much extra info that we can get on these users
#
# the fact e.g. that PlanetLab insists on getting a first_name and last_name is not
# exactly consistent with the GENI spec. of CreateSliver
#
def pg_users_arg(records):
    users = []  
    for record in records:
        if record['type'] != 'user': 
            continue
        user = {'urn': record['reg-urn'],
                'keys': record['reg-keys'],
                }
        users.append(user)
    return users    

def sfa_users_arg (records, slice_record):
    users = []
    for record in records:
        if record['type'] != 'user': 
            continue
        user = {'urn': record['reg-urn'],
                'keys': record['reg-keys'],
                'slice_record': slice_record,
                }
        # fill as much stuff as possible from planetlab or similar
        # note that reg-email is not yet available
        pl_fields = ['email', 'person_id', 'first_name', 'last_name', 'key_ids']
        nitos_fields = [ 'email', 'user_id' ]
        extra_fields = list ( set(pl_fields).union(set(nitos_fields)))
        # try to fill all these in
        for field in extra_fields:
            if record.has_key(field): user[field]=record[field]
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
