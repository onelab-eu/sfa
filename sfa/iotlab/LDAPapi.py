"""
This API is adapted for OpenLDAP. The file contains all LDAP classes and methods
needed to:
- Load the LDAP connection configuration file (login, address..) with LdapConfig
- Connect to LDAP with ldap_co
- Create a unique LDAP login and password for a user based on his email or last
name and first name with LoginPassword.
-  Manage entries in LDAP using SFA records with LDAPapi (Search, Add, Delete,
Modify)

"""
import random
from passlib.hash import ldap_salted_sha1 as lssha

from sfa.util.xrn import get_authority
from sfa.util.sfalogging import logger
from sfa.util.config import Config

import ldap
import ldap.modlist as modlist

import os.path


class LdapConfig():
    """
    Ldap configuration class loads the configuration file and sets the
    ldap IP address, password, people dn, web dn, group dn. All these settings
    were defined in a separate file  ldap_config.py to avoid sharing them in
    the SFA git as it contains sensible information.

    """
    def __init__(self, config_file='/etc/sfa/ldap_config.py'):
        """Loads configuration from file /etc/sfa/ldap_config.py and set the
        parameters for connection to LDAP.

        """

        try:
            execfile(config_file, self.__dict__)

            self.config_file = config_file
            # path to configuration data
            self.config_path = os.path.dirname(config_file)
        except IOError:
            raise IOError, "Could not find or load the configuration file: %s" \
                % config_file


class ldap_co:
    """ Set admin login and server configuration variables."""

    def __init__(self):
        """Fetch LdapConfig attributes (Ldap server connection parameters and
        defines port , version and subtree scope.

        """
        #Iotlab PROD LDAP parameters
        self.ldapserv = None
        ldap_config = LdapConfig()
        self.config = ldap_config
        self.ldapHost = ldap_config.LDAP_IP_ADDRESS
        self.ldapPeopleDN = ldap_config.LDAP_PEOPLE_DN
        self.ldapGroupDN = ldap_config.LDAP_GROUP_DN
        self.ldapAdminDN = ldap_config.LDAP_WEB_DN
        self.ldapAdminPassword = ldap_config.LDAP_WEB_PASSWORD
        self.ldapPort = ldap.PORT
        self.ldapVersion = ldap.VERSION3
        self.ldapSearchScope = ldap.SCOPE_SUBTREE

    def connect(self, bind=True):
        """Enables connection to the LDAP server.

        :param bind: Set the bind parameter to True if a bind is needed
            (for add/modify/delete operations). Set to False otherwise.
        :type bind: boolean
        :returns: dictionary with status of the connection. True if Successful,
            False if not and in this case the error
            message( {'bool', 'message'} ).
        :rtype: dict

        """
        try:
            self.ldapserv = ldap.open(self.ldapHost)
        except ldap.LDAPError, error:
            return {'bool': False, 'message': error}

        # Bind with authentification
        if(bind):
            return self.bind()

        else:
            return {'bool': True}

    def bind(self):
        """ Binding method.

        :returns: dictionary with the bind status. True if Successful,
            False if not and in this case the error message({'bool','message'})
        :rtype: dict

        """
        try:
            # Opens a connection after a call to ldap.open in connect:
            self.ldapserv = ldap.initialize("ldap://" + self.ldapHost)

            # Bind/authenticate with a user with apropriate
            #rights to add objects
            self.ldapserv.simple_bind_s(self.ldapAdminDN,
                                        self.ldapAdminPassword)

        except ldap.LDAPError, error:
            return {'bool': False, 'message': error}

        return {'bool': True}

    def close(self):
        """Close the LDAP connection.

        Can throw an exception if the unbinding fails.

        :returns: dictionary with the bind status if the unbinding failed and
            in this case the dict contains an error message. The dictionary keys
            are : ({'bool','message'})
        :rtype: dict or None

        """
        try:
            self.ldapserv.unbind_s()
        except ldap.LDAPError, error:
            return {'bool': False, 'message': error}


class LoginPassword():
    """

    Class to handle login and password generation, using custom login generation
    algorithm.

    """
    def __init__(self):
        """

        Sets password  and login maximum length, and defines the characters that
        can be found in a random generated password.

        """
        self.login_max_length = 8
        self.length_password = 8
        self.chars_password = ['!', '$', '(',')', '*', '+', ',', '-', '.',
                               '0', '1', '2', '3', '4', '5', '6', '7', '8',
                               '9', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
                               'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q',
                               'R', 'S', 'T',  'U', 'V', 'W', 'X', 'Y', 'Z',
                               '_', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h',
                               'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q',
                               'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                               '\'']

    @staticmethod
    def clean_user_names(record):
        """

        Removes special characters such as '-', '_' , '[', ']' and ' ' from the
        first name and last name.

        :param record: user's record
        :type record: dict
        :returns: lower_first_name and lower_last_name if they were found
            in the user's record. Return None, none otherwise.
        :rtype: string, string or None, None.

        """
        if 'first_name' in record and 'last_name' in record:
            #Remove all special characters from first_name/last name
            lower_first_name = record['first_name'].replace('-', '')\
                .replace('_', '').replace('[', '')\
                .replace(']', '').replace(' ', '')\
                .lower()
            lower_last_name = record['last_name'].replace('-', '')\
                .replace('_', '').replace('[', '')\
                .replace(']', '').replace(' ', '')\
                .lower()
            return lower_first_name, lower_last_name
        else:
            return None, None

    @staticmethod
    def extract_name_from_email(record):
        """

        When there is no valid first name and last name in the record,
        the email is used to generate the login. Here, we assume the email
        is firstname.lastname@something.smthg. The first name and last names
        are extracted from the email, special charcaters are removed and
        they are changed into lower case.

        :param record: user's data
        :type record: dict
        :returns: the first name and last name taken from the user's email.
            lower_first_name, lower_last_name.
        :rtype: string, string

        """

        email = record['email']
        email = email.split('@')[0].lower()
        lower_first_name = None
        lower_last_name = None
        #Assume there is first name and last name in email
        #if there is a  separator
        separator_list = ['.', '_', '-']
        for sep in separator_list:
            if sep in email:
                mail = email.split(sep)
                lower_first_name = mail[0]
                lower_last_name = mail[1]
                break

        #Otherwise just take the part before the @ as the
        #lower_first_name  and lower_last_name
        if lower_first_name is None:
            lower_first_name = email
            lower_last_name = email

        return lower_first_name, lower_last_name

    def get_user_firstname_lastname(self, record):
        """

        Get the user first name and last name from the information we have in
        the record.

        :param record: user's information
        :type record: dict
        :returns: the user's first name and last name.

        .. seealso:: clean_user_names
        .. seealso:: extract_name_from_email

        """
        lower_first_name, lower_last_name = self.clean_user_names(record)

        #No first name and last name  check  email
        if lower_first_name is None and lower_last_name is None:

            lower_first_name, lower_last_name = \
                self.extract_name_from_email(record)

        return lower_first_name, lower_last_name

    def choose_sets_chars_for_login(self, lower_first_name, lower_last_name):
        """

        Algorithm to select sets of characters from the first name and last
        name, depending on the lenght of the last name and the maximum login
        length which in our case is set to 8 characters.

        :param lower_first_name: user's first name in lower case.
        :param lower_last_name: usr's last name in lower case.
        :returns: user's login
        :rtype: string

        """
        length_last_name = len(lower_last_name)
        self.login_max_length = 8

        #Try generating a unique login based on first name and last name

        if length_last_name >= self.login_max_length:
            login = lower_last_name[0:self.login_max_length]
            index = 0
            logger.debug("login : %s index : %s" % (login, index))
        elif length_last_name >= 4:
            login = lower_last_name
            index = 0
            logger.debug("login : %s index : %s" % (login, index))
        elif length_last_name == 3:
            login = lower_first_name[0:1] + lower_last_name
            index = 1
            logger.debug("login : %s index : %s" % (login, index))
        elif length_last_name == 2:
            if len(lower_first_name) >= 2:
                login = lower_first_name[0:2] + lower_last_name
                index = 2
                logger.debug("login : %s index : %s" % (login, index))
            else:
                logger.error("LoginException : \
                            Generation login error with \
                            minimum four characters")

        else:
            logger.error("LDAP LdapGenerateUniqueLogin failed : \
                        impossible to generate unique login for %s %s"
                         % (lower_first_name, lower_last_name))
        return index, login

    def generate_password(self):
        """

        Generate a password upon  adding a new user in LDAP Directory
        (8 characters length). The generated password is composed of characters
        from the chars_password list.

        :returns: the randomly generated password
        :rtype: string

        """
        password = str()

        length = len(self.chars_password)
        for index in range(self.length_password):
            char_index = random.randint(0, length - 1)
            password += self.chars_password[char_index]

        return password

    @staticmethod
    def encrypt_password(password):
        """

        Use passlib library to make a RFC2307 LDAP encrypted password salt size
        is 8, use sha-1 algorithm.

        :param password:  password not encrypted.
        :type password: string
        :returns: Returns encrypted password.
        :rtype: string

        """
        #Keep consistency with Java Iotlab's LDAP API
        #RFC2307SSHAPasswordEncryptor so set the salt size to 8 bytes
        return lssha.encrypt(password, salt_size=8)


class LDAPapi:
    """Defines functions to insert and search entries in the LDAP.

    .. note:: class supposes the unix schema is used

    """
    def __init__(self):
        logger.setLevelDebug()

        #SFA related config

        config = Config()
        self.login_pwd = LoginPassword()
        self.authname = config.SFA_REGISTRY_ROOT_AUTH
        self.conn =  ldap_co()
        self.ldapUserQuotaNFS = self.conn.config.LDAP_USER_QUOTA_NFS
        self.ldapUserUidNumberMin = self.conn.config.LDAP_USER_UID_NUMBER_MIN
        self.ldapUserGidNumber = self.conn.config.LDAP_USER_GID_NUMBER
        self.ldapUserHomePath = self.conn.config.LDAP_USER_HOME_PATH
        self.baseDN = self.conn.ldapPeopleDN
        self.ldapShell = '/bin/bash'


    def LdapGenerateUniqueLogin(self, record):
        """

        Generate login for adding a new user in LDAP Directory
        (four characters minimum length). Get proper last name and
        first name so that the user's login can be generated.

        :param record: Record must contain first_name and last_name.
        :type record: dict
        :returns: the generated login for the user described with record if the
            login generation is successful, None if it fails.
        :rtype: string or None

        """
        #For compatibility with other ldap func
        if 'mail' in record and 'email' not in record:
            record['email'] = record['mail']

        lower_first_name, lower_last_name =  \
            self.login_pwd.get_user_firstname_lastname(record)

        index, login = self.login_pwd.choose_sets_chars_for_login(
            lower_first_name, lower_last_name)

        login_filter = '(uid=' + login + ')'
        get_attrs = ['uid']
        try:
            #Check if login already in use

            while (len(self.LdapSearch(login_filter, get_attrs)) is not 0):

                index += 1
                if index >= 9:
                    logger.error("LoginException : Generation login error \
                                    with minimum four characters")
                else:
                    try:
                        login = \
                            lower_first_name[0:index] + \
                            lower_last_name[0:
                                            self.login_pwd.login_max_length
                                            - index]
                        login_filter = '(uid=' + login + ')'
                    except KeyError:
                        print "lower_first_name - lower_last_name too short"

            logger.debug("LDAP.API \t LdapGenerateUniqueLogin login %s"
                         % (login))
            return login

        except ldap.LDAPError, error:
            logger.log_exc("LDAP LdapGenerateUniqueLogin Error %s" % (error))
            return None

    def find_max_uidNumber(self):
        """Find the LDAP max uidNumber (POSIX uid attribute).

        Used when adding a new user in LDAP Directory

        :returns: max uidNumber + 1
        :rtype: string

        """
        #First, get all the users in the LDAP
        get_attrs = "(uidNumber=*)"
        login_filter = ['uidNumber']

        result_data = self.LdapSearch(get_attrs, login_filter)
        #It there is no user in LDAP yet, First LDAP user
        if result_data == []:
            max_uidnumber = self.ldapUserUidNumberMin
        #Otherwise, get the highest uidNumber
        else:
            uidNumberList = [int(r[1]['uidNumber'][0])for r in result_data]
            logger.debug("LDAPapi.py \tfind_max_uidNumber  \
                            uidNumberList %s " % (uidNumberList))
            max_uidnumber = max(uidNumberList) + 1

        return str(max_uidnumber)


    def get_ssh_pkey(self, record):
        """TODO ; Get ssh public key from sfa record
        To be filled by N. Turro ? or using GID pl way?

        """
        return 'A REMPLIR '

    @staticmethod
    #TODO Handle OR filtering in the ldap query when
    #dealing with a list of records instead of doing a for loop in GetPersons
    def make_ldap_filters_from_record(record=None):
        """Helper function to make LDAP filter requests out of SFA records.

        :param record: user's sfa record. Should contain first_name,last_name,
            email or mail, and if the record is enabled or not. If the dict
            record does not have all of these, must at least contain the user's
            email.
        :type record: dict
        :returns: LDAP request
        :rtype: string

        """
        req_ldap = ''
        req_ldapdict = {}
        if record :
            if 'first_name' in record and 'last_name' in record:
                if record['first_name'] != record['last_name']:
                    req_ldapdict['cn'] = str(record['first_name'])+" "\
                        + str(record['last_name'])
            if 'email' in record:
                req_ldapdict['mail'] = record['email']
            if 'mail' in record:
                req_ldapdict['mail'] = record['mail']
            if 'enabled' in record:
                if record['enabled'] is True:
                    req_ldapdict['shadowExpire'] = '-1'
                else:
                    req_ldapdict['shadowExpire'] = '0'

            #Hrn should not be part of the filter because the hrn
            #presented by a certificate of a SFA user not imported in
            #Iotlab  does not include the iotlab login in it
            #Plus, the SFA user may already have an account with iotlab
            #using another login.

            logger.debug("\r\n \t LDAP.PY make_ldap_filters_from_record \
                                record %s req_ldapdict %s"
                         % (record, req_ldapdict))

            for k in req_ldapdict:
                req_ldap += '(' + str(k) + '=' + str(req_ldapdict[k]) + ')'
            if len(req_ldapdict.keys()) >1 :
                req_ldap = req_ldap[:0]+"(&"+req_ldap[0:]
                size = len(req_ldap)
                req_ldap = req_ldap[:(size-1)] + ')' + req_ldap[(size-1):]
        else:
            req_ldap = "(cn=*)"

        return req_ldap

    def make_ldap_attributes_from_record(self, record):
        """

        When adding a new user to Iotlab's LDAP, creates an attributes
        dictionnary from the SFA record understandable by LDAP. Generates the
        user's LDAP login.User is automatically validated (account enabled)
        and described as a SFA USER FROM OUTSIDE IOTLAB.

        :param record: must contain the following keys and values:
            first_name, last_name, mail, pkey (ssh key).
        :type record: dict
        :returns: dictionary of attributes using LDAP data structure model.
        :rtype: dict

        """

        attrs = {}
        attrs['objectClass'] = ["top", "person", "inetOrgPerson",
                                "organizationalPerson", "posixAccount",
                                "shadowAccount", "systemQuotas",
                                "ldapPublicKey"]

        attrs['uid'] = self.LdapGenerateUniqueLogin(record)
        try:
            attrs['givenName'] = str(record['first_name']).lower().capitalize()
            attrs['sn'] = str(record['last_name']).lower().capitalize()
            attrs['cn'] = attrs['givenName'] + ' ' + attrs['sn']
            attrs['gecos'] = attrs['givenName'] + ' ' + attrs['sn']

        except KeyError:
            attrs['givenName'] = attrs['uid']
            attrs['sn'] = attrs['uid']
            attrs['cn'] = attrs['uid']
            attrs['gecos'] = attrs['uid']

        attrs['quota'] = self.ldapUserQuotaNFS
        attrs['homeDirectory'] = self.ldapUserHomePath + attrs['uid']
        attrs['loginShell'] = self.ldapShell
        attrs['gidNumber'] = self.ldapUserGidNumber
        attrs['uidNumber'] = self.find_max_uidNumber()
        attrs['mail'] = record['mail'].lower()
        try:
            attrs['sshPublicKey'] = record['pkey']
        except KeyError:
            attrs['sshPublicKey'] = self.get_ssh_pkey(record)


        #Password is automatically generated because SFA user don't go
        #through the Iotlab website  used to register new users,
        #There is no place in SFA where users can enter such information
        #yet.
        #If the user wants to set his own password , he must go to the Iotlab
        #website.
        password = self.login_pwd.generate_password()
        attrs['userPassword'] = self.login_pwd.encrypt_password(password)

        #Account automatically validated (no mail request to admins)
        #Set to 0 to disable the account, -1 to enable it,
        attrs['shadowExpire'] = '-1'

        #Motivation field in Iotlab
        attrs['description'] = 'SFA USER FROM OUTSIDE SENSLAB'

        attrs['ou'] = 'SFA'         #Optional: organizational unit
        #No info about those here:
        attrs['l'] = 'To be defined'#Optional: Locality.
        attrs['st'] = 'To be defined' #Optional: state or province (country).

        return attrs



    def LdapAddUser(self, record) :
        """Add SFA user to LDAP if it is not in LDAP  yet.

        :param record: dictionnary with the user's data.
        :returns: a dictionary with the status (Fail= False, Success= True)
            and the uid of the newly added user if successful, or the error
            message it is not. Dict has keys bool and message in case of
            failure, and bool uid in case of success.
        :rtype: dict

        .. seealso:: make_ldap_filters_from_record

        """
        logger.debug(" \r\n \t LDAP LdapAddUser \r\n\r\n ================\r\n ")
        user_ldap_attrs = self.make_ldap_attributes_from_record(record)

        #Check if user already in LDAP wih email, first name and last name
        filter_by = self.make_ldap_filters_from_record(user_ldap_attrs)
        user_exist = self.LdapSearch(filter_by)
        if user_exist:
            logger.warning(" \r\n \t LDAP LdapAddUser user %s %s \
                        already exists" % (user_ldap_attrs['sn'],
                           user_ldap_attrs['mail']))
            return {'bool': False}

        #Bind to the server
        result = self.conn.connect()

        if(result['bool']):

            # A dict to help build the "body" of the object
            logger.debug(" \r\n \t LDAP LdapAddUser attrs %s "
                         % user_ldap_attrs)

            # The dn of our new entry/object
            dn = 'uid=' + user_ldap_attrs['uid'] + "," + self.baseDN

            try:
                ldif = modlist.addModlist(user_ldap_attrs)
                logger.debug("LDAPapi.py add attrs %s \r\n  ldif %s"
                             % (user_ldap_attrs, ldif))
                self.conn.ldapserv.add_s(dn, ldif)

                logger.info("Adding user %s login %s in LDAP"
                            % (user_ldap_attrs['cn'], user_ldap_attrs['uid']))
            except ldap.LDAPError, error:
                logger.log_exc("LDAP Add Error %s" % error)
                return {'bool': False, 'message': error}

            self.conn.close()
            return {'bool': True, 'uid': user_ldap_attrs['uid']}
        else:
            return result

    def LdapDelete(self, person_dn):
        """Deletes a person in LDAP. Uses the dn of the user.

        :param person_dn: user's ldap dn.
        :type person_dn: string
        :returns: dictionary with bool True if successful, bool False
            and the error if not.
        :rtype: dict

        """
        #Connect and bind
        result =  self.conn.connect()
        if(result['bool']):
            try:
                self.conn.ldapserv.delete_s(person_dn)
                self.conn.close()
                return {'bool': True}

            except ldap.LDAPError, error:
                logger.log_exc("LDAP Delete Error %s" % error)
                return {'bool': False, 'message': error}

    def LdapDeleteUser(self, record_filter):
        """Deletes a SFA person in LDAP, based on the user's hrn.

        :param record_filter: Filter to find the user to be deleted. Must
            contain at least the user's email.
        :type record_filter: dict
        :returns: dict with bool True if successful, bool False and error
            message otherwise.
        :rtype: dict

        .. seealso:: LdapFindUser docstring for more info on record filter.
        .. seealso:: LdapDelete for user deletion

        """
        #Find uid of the  person
        person = self.LdapFindUser(record_filter, [])
        logger.debug("LDAPapi.py \t LdapDeleteUser record %s person %s"
                     % (record_filter, person))

        if person:
            dn = 'uid=' + person['uid'] + "," + self.baseDN
        else:
            return {'bool': False}

        result = self.LdapDelete(dn)
        return result

    def LdapModify(self, dn, old_attributes_dict, new_attributes_dict):
        """ Modifies a LDAP entry, replaces user's old attributes with
        the new ones given.

        :param dn: user's absolute name  in the LDAP hierarchy.
        :param old_attributes_dict: old user's attributes. Keys must match
            the ones used in the LDAP model.
        :param new_attributes_dict: new user's attributes. Keys must match
            the ones used in the LDAP model.
        :type dn: string
        :type old_attributes_dict: dict
        :type new_attributes_dict: dict
        :returns: dict bool True if Successful, bool False if not.
        :rtype: dict

        """

        ldif = modlist.modifyModlist(old_attributes_dict, new_attributes_dict)
        # Connect and bind/authenticate
        result = self.conn.connect()
        if (result['bool']):
            try:
                self.conn.ldapserv.modify_s(dn, ldif)
                self.conn.close()
                return {'bool': True}
            except ldap.LDAPError, error:
                logger.log_exc("LDAP LdapModify Error %s" % error)
                return {'bool': False}


    def LdapModifyUser(self, user_record, new_attributes_dict):
        """

        Gets the record from one user based on the user sfa recordand changes
        the attributes according to the specified new_attributes. Do not use
        this if we need to modify the uid. Use a ModRDN operation instead
        ( modify relative DN ).

        :param user_record: sfa user record.
        :param new_attributes_dict: new user attributes, keys must be the
            same as the LDAP model.
        :type user_record: dict
        :type new_attributes_dict: dict
        :returns: bool True if successful, bool False if not.
        :rtype: dict

        .. seealso:: make_ldap_filters_from_record for info on what is mandatory
            in the user_record.
        .. seealso:: make_ldap_attributes_from_record for the LDAP objectclass.

        """
        if user_record is None:
            logger.error("LDAP \t LdapModifyUser Need user record  ")
            return {'bool': False}

        #Get all the attributes of the user_uid_login
        #person = self.LdapFindUser(record_filter,[])
        req_ldap = self.make_ldap_filters_from_record(user_record)
        person_list = self.LdapSearch(req_ldap, [])
        logger.debug("LDAPapi.py \t LdapModifyUser person_list : %s"
                     % (person_list))

        if person_list and len(person_list) > 1:
            logger.error("LDAP \t LdapModifyUser Too many users returned")
            return {'bool': False}
        if person_list is None:
            logger.error("LDAP \t LdapModifyUser  User %s doesn't exist "
                         % (user_record))
            return {'bool': False}

        # The dn of our existing entry/object
        #One result only from ldapSearch
        person = person_list[0][1]
        dn = 'uid=' + person['uid'][0] + "," + self.baseDN

        if new_attributes_dict:
            old = {}
            for k in new_attributes_dict:
                if k not in person:
                    old[k] = ''
                else:
                    old[k] = person[k]
            logger.debug(" LDAPapi.py \t LdapModifyUser  new_attributes %s"
                         % (new_attributes_dict))
            result = self.LdapModify(dn, old, new_attributes_dict)
            return result
        else:
            logger.error("LDAP \t LdapModifyUser  No new attributes given. ")
            return {'bool': False}


    def LdapMarkUserAsDeleted(self, record):
        """

        Sets shadowExpire to 0, disabling the user in LDAP. Calls LdapModifyUser
        to change the shadowExpire of the user.

        :param record: the record of the user who has to be disabled.
            Should contain first_name,last_name, email or mail, and if the
            record is enabled or not. If the dict record does not have all of
            these, must at least contain the user's email.
        :type record: dict
        :returns: {bool: True} if successful or {bool: False} if not
        :rtype: dict

        .. seealso:: LdapModifyUser, make_ldap_attributes_from_record
        """

        new_attrs = {}
        #Disable account
        new_attrs['shadowExpire'] = '0'
        logger.debug(" LDAPapi.py \t LdapMarkUserAsDeleted ")
        ret = self.LdapModifyUser(record, new_attrs)
        return ret

    def LdapResetPassword(self, record):
        """Resets password for the user whose record is the parameter and
        changes the corresponding entry in the LDAP.

        :param record: user's sfa record whose Ldap password must be reset.
            Should contain first_name,last_name,
            email or mail, and if the record is enabled or not. If the dict
            record does not have all of these, must at least contain the user's
            email.
        :type record: dict
        :returns: return value of LdapModifyUser. True if successful, False
            otherwise.

        .. seealso:: LdapModifyUser, make_ldap_attributes_from_record

        """
        password = self.login_pwd.generate_password()
        attrs = {}
        attrs['userPassword'] = self.login_pwd.encrypt_password(password)
        logger.debug("LDAP LdapResetPassword encrypt_password %s"
                     % (attrs['userPassword']))
        result = self.LdapModifyUser(record, attrs)
        return result


    def LdapSearch(self, req_ldap=None, expected_fields=None):
        """
        Used to search directly in LDAP, by using ldap filters and return
        fields. When req_ldap is None, returns all the entries in the LDAP.

        :param req_ldap: ldap style request, with appropriate filters,
             example: (cn=*).
        :param expected_fields: Fields in the user ldap entry that has to be
            returned. If None is provided, will return 'mail', 'givenName',
            'sn', 'uid', 'sshPublicKey', 'shadowExpire'.
        :type req_ldap: string
        :type expected_fields: list

        .. seealso:: make_ldap_filters_from_record for req_ldap format.

        """
        result = self.conn.connect(bind=False)
        if (result['bool']):

            return_fields_list = []
            if expected_fields is None:
                return_fields_list = ['mail', 'givenName', 'sn', 'uid',
                                      'sshPublicKey', 'shadowExpire']
            else:
                return_fields_list = expected_fields
            #No specifc request specified, get the whole LDAP
            if req_ldap is None:
                req_ldap = '(cn=*)'

            logger.debug("LDAP.PY \t LdapSearch  req_ldap %s \
                                    return_fields_list %s" \
                                    %(req_ldap, return_fields_list))

            try:
                msg_id = self.conn.ldapserv.search(
                    self.baseDN, ldap.SCOPE_SUBTREE,
                    req_ldap, return_fields_list)
                #Get all the results matching the search from ldap in one
                #shot (1 value)
                result_type, result_data = \
                    self.conn.ldapserv.result(msg_id, 1)

                self.conn.close()

                logger.debug("LDAP.PY \t LdapSearch  result_data %s"
                             % (result_data))

                return result_data

            except ldap.LDAPError, error:
                logger.log_exc("LDAP LdapSearch Error %s" % error)
                return []

            else:
                logger.error("LDAP.PY \t Connection Failed")
                return

    def _process_ldap_info_for_all_users(self, result_data):
        """Process the data of all enabled users in LDAP.

        :param result_data: Contains information of all enabled users in LDAP
            and is coming from LdapSearch.
        :param result_data: list

        .. seealso:: LdapSearch

        """
        results = []
        logger.debug(" LDAP.py _process_ldap_info_for_all_users result_data %s "
                     % (result_data))
        for ldapentry in result_data:
            logger.debug(" LDAP.py _process_ldap_info_for_all_users \
                        ldapentry name : %s " % (ldapentry[1]['uid'][0]))
            tmpname = ldapentry[1]['uid'][0]
            hrn = self.authname + "." + tmpname

            tmpemail = ldapentry[1]['mail'][0]
            if ldapentry[1]['mail'][0] == "unknown":
                tmpemail = None

            try:
                results.append({
                    'type': 'user',
                    'pkey': ldapentry[1]['sshPublicKey'][0],
                    #'uid': ldapentry[1]['uid'][0],
                    'uid': tmpname ,
                    'email':tmpemail,
                    #'email': ldapentry[1]['mail'][0],
                    'first_name': ldapentry[1]['givenName'][0],
                    'last_name': ldapentry[1]['sn'][0],
                    #'phone': 'none',
                    'serial': 'none',
                    'authority': self.authname,
                    'peer_authority': '',
                    'pointer': -1,
                    'hrn': hrn,
                              })
            except KeyError, error:
                logger.log_exc("LDAPapi.PY \t LdapFindUser EXCEPTION %s"
                               % (error))
                return

        return results

    def _process_ldap_info_for_one_user(self, record, result_data):
        """

        Put the user's ldap data into shape. Only deals with one user
        record and one user data from ldap.

        :param record: user record
        :param result_data: Raw ldap data coming from LdapSearch
        :returns: user's data dict with 'type','pkey','uid', 'email',
            'first_name' 'last_name''serial''authority''peer_authority'
            'pointer''hrn'
        :type record: dict
        :type result_data: list
        :rtype :dict

        """
        #One entry only in the ldap data because we used a  filter
        #to find one user only
        ldapentry = result_data[0][1]
        logger.debug("LDAP.PY \t LdapFindUser ldapentry %s" % (ldapentry))
        tmpname = ldapentry['uid'][0]

        tmpemail = ldapentry['mail'][0]
        if ldapentry['mail'][0] == "unknown":
            tmpemail = None

        parent_hrn = None
        peer_authority = None
        if 'hrn' in record:
            hrn = record['hrn']
            parent_hrn = get_authority(hrn)
            if parent_hrn != self.authname:
                peer_authority = parent_hrn
            #In case the user was not imported from Iotlab LDAP
            #but from another federated site, has an account in
            #iotlab but currently using his hrn from federated site
            #then the login is different from the one found in its hrn
            if tmpname != hrn.split('.')[1]:
                hrn = None
        else:
            hrn = None

        results = {
            'type': 'user',
            'pkey': ldapentry['sshPublicKey'],
            #'uid': ldapentry[1]['uid'][0],
            'uid': tmpname,
            'email': tmpemail,
            #'email': ldapentry[1]['mail'][0],
            'first_name': ldapentry['givenName'][0],
            'last_name': ldapentry['sn'][0],
            #'phone': 'none',
            'serial': 'none',
            'authority': parent_hrn,
            'peer_authority': peer_authority,
            'pointer': -1,
            'hrn': hrn,
                    }
        return results

    def LdapFindUser(self, record=None, is_user_enabled=None,
                     expected_fields=None):
        """

        Search a SFA user with a hrn. User should be already registered
        in Iotlab LDAP.

        :param record: sfa user's record. Should contain first_name,last_name,
            email or mail. If no record is provided, returns all the users found
            in LDAP.
        :type record: dict
        :param is_user_enabled: is the user's iotlab account already valid.
        :type is_user_enabled: Boolean.
        :returns: LDAP entries from ldap matching the filter provided. Returns
            a single entry if one filter has been given and a list of
            entries otherwise.
        :rtype:  dict or list

        """
        custom_record = {}
        if is_user_enabled:
            custom_record['enabled'] = is_user_enabled
        if record:
            custom_record.update(record)

        req_ldap = self.make_ldap_filters_from_record(custom_record)
        return_fields_list = []
        if expected_fields is None:
            return_fields_list = ['mail', 'givenName', 'sn', 'uid',
                                  'sshPublicKey']
        else:
            return_fields_list = expected_fields

        result_data = self.LdapSearch(req_ldap, return_fields_list)
        logger.debug("LDAP.PY \t LdapFindUser  result_data %s" % (result_data))

        if len(result_data) == 0:
            return None
        #Asked for a specific user
        if record is not None:
            results = self._process_ldap_info_for_one_user(record, result_data)

        else:
        #Asked for all users in ldap
            results = self._process_ldap_info_for_all_users(result_data)
        return results