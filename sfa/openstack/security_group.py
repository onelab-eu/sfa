from sfa.util.sfalogging import logger

class SecurityGroup:

    def __init__(self, driver):
        self.driver = driver

        
    def create_security_group(self, name):
        conn = self.driver.euca_shell.get_euca_connection()
        try:
            conn.create_security_group(name=name, description="")
        except Exception, ex:
            logger.log_exc("Failed to add security group")

    def delete_security_group(self, name):
        conn = self.driver.euca_shell.get_euca_connection()
        try:
            conn.delete_security_group(name=name)
        except Exception, ex:
            logger.log_exc("Failed to delete security group")


    def _validate_port_range(self, port_range):
        from_port = to_port = None
        if isinstance(port_range, str):
            ports = port_range.split(':')
            if len(ports) > 1:
                from_port = int(ports[0])
                to_port = int(ports[1])
            else:
                from_port = to_port = int(ports[0])
        return (from_port, to_port)

    def _validate_icmp_type_code(self, icmp_type_code):
        from_port = to_port = None
        if isinstance(icmp_type_code, str):
            code_parts = icmp_type_code.split(':')
            if len(code_parts) > 1:
                try:
                    from_port = int(code_parts[0])
                    to_port = int(code_parts[1])
                except ValueError:
                    logger.error('port must be an integer.')
        return (from_port, to_port)


    def add_rule_to_group(self, group_name=None, protocol='tcp', cidr_ip='0.0.0.0/0',
                          port_range=None, icmp_type_code=None,
                          source_group_name=None, source_group_owner_id=None):

        from_port, to_port = self._validate_port_range(port_range)
        icmp_type = self._validate_icmp_type_code(icmp_type_code)
        if icmp_type and icmp_type[0] and icmp_type[1]:
            from_port, to_port = icmp_type[0], icmp_type[1]

        if group_name:
            conn = self.driver.euca_shell.get_euca_connection()
            try:
                conn.authorize_security_group(
                    group_name=group_name,
                    src_security_group_name=source_group_name,
                    src_security_group_owner_id=source_group_owner_id,
                    ip_protocol=protocol,
                    from_port=from_port,
                    to_port=to_port,
                    cidr_ip=cidr_ip,
                    )
            except Exception, ex:
                logger.log_exc("Failed to add rule to group %s" % group_name)


    def remove_rule_from_group(self, group_name=None, protocol='tcp', cidr_ip='0.0.0.0/0',
                          port_range=None, icmp_type_code=None,
                          source_group_name=None, source_group_owner_id=None):

        from_port, to_port = self._validate_port_range(port_range)
        icmp_type = self._validate_icmp_type_code(icmp_type_code)
        if icmp_type:
            from_port, to_port = icmp_type[0], icmp_type[1]

        if group_name:
            conn = self.driver.euca_shell.get_euca_connection()
            try:
                conn.revoke_security_group(
                    group_name=group_name,
                    src_security_group_name=source_group_name,
                    src_security_group_owner_id=source_group_owner_id,
                    ip_protocol=protocol,
                    from_port=from_port,
                    to_port=to_port,
                    cidr_ip=ip,
                    )
            except Exception, ex:
                logger.log_exc("Failed to remove rule from group %s" % group_name) 
             
