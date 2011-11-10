from sfa.rspecs.elements.element import Element  
from sfa.rspecs.elements.execute import Execute  
from sfa.rspecs.elements.install import Install  
from sfa.rspecs.elements.login import Login

class PGv2Services:
    @staticmethod
    def add_services(xml, services):
        for service in services:
            service_elem = etree.SubElement(xml, 'service')
            Element.add(service_elem, 'install', service.get('install', []), Install.fields) 
            Element.add(service_elem, 'execute', service.get('execute', []), Execute.fields) 
            Element.add(service_elem, 'login', service.get('login', []), Login.fields) 
              
    @staticmethod
    def get_services(xml):
        services = []
        for services_elem in xml.xpath('./default:services | ./services'):
            service = Services(services_elem.attrib, services_elem)
            service['install'] = Element.get(service_elem, './default:install | ./install', Install)
            service['execute'] = Element.get(service_elem, './default:execute | ./execute', Execute)
            service['login'] = Element.get(service_elem, './default:login | ./login', Login)
            services.append(service)  
        return services

