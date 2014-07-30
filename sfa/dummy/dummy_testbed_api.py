import SimpleXMLRPCServer
import time

dummy_api_addr = ("localhost", 8080)

# Fake Testbed DB 

nodes_list = []
for i in range(1,11):
    node = {'hostname': 'node'+str(i)+'.dummy-testbed.org', 'type': 'dummy-node', 'node_id': i}
    nodes_list.append(node)

slices_list = []
for i in range(1,3):
    slice = {'slice_name': 'slice'+str(i), 
             'user_ids': range(i,4,2), 
             'slice_id': i, 
             'node_ids': range(i,10,2),
             'enabled': True,
             'expires': int(time.time())+60*60*24*30}
    slices_list.append(slice)

users_list = []
for i in range(1,5):
    user = {'user_name': 'user'+str(i), 'user_id': i, 'email': 'user'+str(i)+'@dummy-testbed.org', 'keys': ['user_ssh_pub_key_'+str(i)]}
    users_list.append(user)

DB = {'nodes_list': nodes_list,'node_index': 11, 'slices_list': slices_list, 'slice_index': 3, 'users_list': users_list, 'user_index': 5}

#Filter function gor the GET methods

def FilterList(myfilter, mylist):
    result = []
    result.extend(mylist)
    for item in mylist:
         for key in myfilter.keys():
             if 'ids' in key:
                 pass
             else:
                 if isinstance(myfilter[key], str) and myfilter[key] != item[key] or isinstance(myfilter[key], list) and item[key] not in myfilter[key]:
                     result.remove(item)
                     break
    return result


# RPC functions definition
#GET
def GetTestbedInfo():
    return {'name': 'dummy', 'longitude': 123456, 'latitude': 654321, 'domain':'dummy-testbed.org'}

def GetNodes(filter=None):
    if filter is None: filter={}
    global DB
    result = []
    result.extend(DB['nodes_list'])
    if 'node_ids' in filter:
        for node in DB['nodes_list']:
             if node['node_id'] not in filter['node_ids']:
                 result.remove(node)
    if filter:
        result = FilterList(filter, result)
    return result

def GetSlices(filter=None):
    if filter is None: filter={}
    global DB
    result = []
    result.extend(DB['slices_list'])
    if 'slice_ids' in filter:
        for slice in DB['slices_list']:
             if slice['slice_id'] not in filter['slice_ids']:
                 result.remove(slice)

    if filter:
        result = FilterList(filter, result)
    return result


def GetUsers(filter=None):
    if filter is None: filter={}
    global DB
    result = []
    result.extend(DB['users_list'])
    if 'user_ids' in filter:
        for user in DB['users_list']:
             if user['user_id'] not in filter['user_ids']:
                 result.remove(user)

    if filter:
        result = FilterList(filter, result)
    return result


#def GetKeys():
    


#add

def AddNode(node):
    global DB
    if not isinstance(node, dict):
        return False
    for key in node.keys():
         if key not in ['hostname', 'type']:
             return False
    node['node_id'] = DB['node_index']
    DB['node_index'] += 1
    DB['nodes_list'].append(node)    
    return node['node_id']

def AddSlice(slice):
    global DB
    if not isinstance(slice, dict):
        return False
    for key in slice.keys():
         if key not in ['slice_name', 'user_ids', 'node_ids', 'enabled', 'expires']:
             return False
    slice['slice_id'] = DB['slice_index']
    slice['expires'] = int(time.time())+60*60*24*30
    DB['slice_index'] += 1
    DB['slices_list'].append(slice)
    return slice['slice_id']


def AddUser(user):
    global DB
    if not isinstance(user, dict):
        return False
    for key in user.keys():
         if key not in ['user_name', 'email', 'keys']:
             return False
    user['user_id'] = DB['user_index']
    DB['user_index'] += 1
    DB['users_list'].append(user)
    return user['user_id']


def AddUserKey(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for user in DB['users_list']:
             if param['user_id'] == user['user_id']:
                 if 'keys' in user.keys():
                     user['keys'].append(param['key'])
                 else:
                    user['keys'] = [param['key']] 
                 return True
        return False
    except:
        return False

def AddUserToSlice(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for slice in DB['slices_list']:
             if param['slice_id'] == slice['slice_id']:
                 if not 'user_ids' in slice: slice['user_ids'] = []
                 slice['user_ids'].append(param['user_id'])
                 return True
        return False
    except:
        return False

def AddSliceToNodes(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for slice in DB['slices_list']:
             if param['slice_id'] == slice['slice_id']:
                 if not 'node_ids' in slice: slice['node_ids'] = []
                 slice['node_ids'].extend(param['node_ids'])
                 return True
        return False
    except:
        return False


#Delete

def DeleteNode(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for node in DB['nodes_list']:
             if param['node_id'] == node['node_id']:
                 DB['nodes_list'].remove(node)
                 for slice in DB['slices_list']:
                      if param['node_id'] in slice['node_ids']:
                          slice['node_ids'].remove(param['node_id'])
                          return True    
        return False
    except:  
        return False


def DeleteSlice(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for slice in DB['slices_list']:
             if param['slice_id'] == slice['slice_id']:
                 DB['slices_list'].remove(slice)
                 return True
        return False
    except:
        return False


def DeleteUser(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for user in DB['users_list']:
             if param['user_id'] == user['user_id']:
                 DB['users_list'].remove(user)
                 for slice in DB['slices_list']:
                      if param['user_id'] in slice['user_ids']:
                          slice['user_ids'].remove(param['user_id'])
                          return True
        return False
    except:
        return False
    

def DeleteKey(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for user in DB['users_list']:
             if param['key'] in user['keys']:
                 user['keys'].remove(param['key'])
                 return True
        return False
    except:
        return False

def DeleteUserFromSlice(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for slice in DB['slices_list']:
             if param['slice_id'] == slice['slice_id'] and param['user_id'] in slice['user_ids']:
                 slice['user_ids'].remove(param['user_id'])
                 return True
        return False
    except:
        return False
             

def DeleteSliceFromNodes(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for slice in DB['slices_list']:
             if param['slice_id'] == slice['slice_id']:
                 for node_id in param['node_ids']:
                      if node_id in slice['node_ids']: slice['node_ids'].remove(node_id)
                 return True
        return False
    except:
        return False


#Update

def UpdateNode(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for node in DB['nodes_list']:
             if param['node_id'] == node['node_id']:
                 for key in param['fields'].keys():
                      if key in ['hostname', 'type']:
                          node[key] = param['fields'][key]
                 return True
        return False
    except:
        return False


def UpdateSlice(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for slice in DB['slices_list']:
             if param['slice_id'] == slice['slice_id']:
                 for key in param['fields'].keys():
                      if key in ['slice_name']:
                          slice[key] = param['fields'][key]
                 return True
        return False
    except:
        return False


def UpdateUser(param):
    global DB
    if not isinstance(param, dict):
        return False
    try:
        for user in DB['users_list']:
             if param['user_id'] == user['user_id']:
                 for key in param['fields'].keys():
                      if key in ['user_name', 'email']:
                          user[key] = param['fields'][key]
                 return True
        return False
    except:
        return False




# Instantiate the XMLRPC server 
dummy_api_server = SimpleXMLRPCServer.SimpleXMLRPCServer(dummy_api_addr)

# RPC functions registration
dummy_api_server.register_function(GetTestbedInfo)
dummy_api_server.register_function(GetNodes)
dummy_api_server.register_function(GetSlices)
dummy_api_server.register_function(GetUsers)
dummy_api_server.register_function(AddNode)
dummy_api_server.register_function(AddSlice)
dummy_api_server.register_function(AddUser)
dummy_api_server.register_function(AddUserKey)
dummy_api_server.register_function(AddUserToSlice)
dummy_api_server.register_function(AddSliceToNodes)
dummy_api_server.register_function(DeleteNode)
dummy_api_server.register_function(DeleteSlice)
dummy_api_server.register_function(DeleteUser)
dummy_api_server.register_function(DeleteKey)
dummy_api_server.register_function(DeleteUserFromSlice)
dummy_api_server.register_function(DeleteSliceFromNodes)
dummy_api_server.register_function(UpdateNode)
dummy_api_server.register_function(UpdateSlice)
dummy_api_server.register_function(UpdateUser)


# Register Introspective functions
dummy_api_server.register_introspection_functions()

# Handle requests
dummy_api_server.serve_forever()



