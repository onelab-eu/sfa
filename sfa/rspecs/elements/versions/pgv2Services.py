from sfa.rspecs.elements.element import Element  
from sfa.rspecs.elements.execute import Execute  
from sfa.rspecs.elements.install import Install  
from sfa.rspecs.elements.services import ServicesElement  
from sfa.rspecs.elements.login import Login

class PGv2Services:
    @staticmethod
    def add_services(xml, services):
        if not services:
            return 
        for service in services:
            service_elem = xml.add_element('services')
            child_elements = {'install': Install.fields,
                              'execute': Execute.fields,
                              'login': Login.fields}
            for (name, fields) in child_elements.items():
                child = service.get(name)
                if not child: 
                    continue
                if isinstance(child, dict):
                    service_elem.add_instance(name, child, fields)
                elif isinstance(child, list):
                    for obj in child:
                        service_elem.add_instance(name, obj, fields)

#            # add ssh_users
#            if service['services_user']:
#                for ssh_user in service['services_user']:
#                    ssh_user_elem = service_elem.add_element('{%s}services_user' % xml.namespaces['ssh-user'],
#                                                             login=ssh_user['login'],
#                                                             user_urn=ssh_user['user_urn'])
#                    for key in ssh_user['keys']:
#                        pkey_elem = ssh_user_elem.add_element('{%s}public_key' % xml.namespaces['ssh-user'])
#                        pkey_elem.element.text=key
              
    @staticmethod
    def get_services(xml):
        services = []
        for services_elem in xml.xpath('./default:services | ./services'):
            service = ServicesElement(services_elem.attrib, services_elem)
            # get install 
            install_elems = services_elem.xpath('./default:install | ./install')
            service['install'] = [install_elem.get_instance(Install) for install_elem in install_elems]
            # get execute
            execute_elems = services_elem.xpath('./default:execute | ./execute')
            service['execute'] = [execute_elem.get_instance(Execute) for execute_elem in execute_elems]
            # get login
            login_elems = services_elem.xpath('./default:login | ./login')
            service['login'] = [login_elem.get_instance(Login) for login_elem in login_elems]

#            ssh_user_elems = services_elem.xpath('./ssh-user:service_user | ./service_user')
#            services_user = []
#            for ssh_user_elem in ssh_user_elems:
#                services_user = ssh_user_elem.get_instance(None, fields=['login', 'user_urn'])
#            service['services_user'] = services_user

            services.append(service)  
        return services

