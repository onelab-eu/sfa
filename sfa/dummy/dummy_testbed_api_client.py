import xmlrpclib
from datetime import datetime
import time

dummy_url = "http://localhost:8080"
dummy_api = xmlrpclib.ServerProxy(dummy_url)

# Add a user:
my_user_id = dummy_api.AddUser({'email': 'john.doe@test.net', 'user_name': 'john.doe', 'keys': ['copy here your ssh-rsa public key']})
# Attach the user with the slice named : slice2 :
dummy_api.AddUserToSlice({'slice_id': 2, 'user_id': my_user_id})

# Display the list of users
print dummy_api.GetUsers()
# Display the list of slices
print dummy_api.GetSlices()
