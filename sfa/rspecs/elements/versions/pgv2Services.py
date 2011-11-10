from lxml import etree
from sfa.util.plxrn import PlXrn
from sfa.util.xrn import Xrn
from sfa.rspecs.elements.execute import Execute  
from sfa.rspecs.elements.install import Install  
from sfa.rspecs.elements.login import Login
from sfa.rspecs.rspec_elements import RSpecElement, RSpecElements

class PGv2Services:
    elements = {
        'services': RSpecElement(RSpecElements.SERVICES, '//default:services | //services'),
        'install': RSpecElement(RSpecElements.INSTALL, './default:install | ./install'),
        'execute': RSpecElement(RSpecElements.EXECUTE, './default:execute | ./execute'),
        'login': RSpecElement(RSpecElements.LOGIN, './default:login | ./login'),
    }  
    
    @staticmethod
    def add_services(xml, services):
        for service in services:
            service_elem = etree.SubElement(xml, 'service')
            for install in service.get('install', []):
                install_elem = etree.SubElement(service_elem, 'install')
                for field in Install.fields:
                    if field in install:
                        install_elem.set(field, install[field])
            for execute in service.get('execute', []):
                execute_elem = etree.SubElement(service_elem, 'execute')
                for field in Execute.fields:
                    if field in execute:
                        execute_elem.set(field, execute[field])
            for login in service.get('login', []):
                login_elem = etree.SubElement(service_elem, 'login')
                for field in Login.fields:
                    if field in login:
                        login_elem.set(field, login[field]) 

              
    @staticmethod
    def get_services(xml):
        services = []
        for services_elem in xml.xpath(PGv2Services.elements['services'].path):
            service = Services(services_elem.attrib, services_elem)
            
            # get install elements
            service['install'] = []
            for install_elem in xml.xpath(PGv2Services.elements['install'].path):
                install = Install(install_elem.attrib, install_elem)
                service['install'].append(install)
            
            # get execute elements
            service['execute'] = []
            for execute_elem in xml.xpath(PGv2Services.elements['execute'].path):
                execute = Execute(execute_elem.attrib, execute_elem)
                service['execute'].append(execute)

            # get login elements
            service['login'] = []
            for login_elem in xml.xpath(PGv2Services.elements['login'].path):
                login = Login(login_elem.attrib, login_elem)
                service['login'].append(login)             

            services.append(service)  
 
        return services

