# Taken from bwlimit.py
#
# See tc_util.c and http://physics.nist.gov/cuu/Units/binary.html. Be
# warned that older versions of tc interpret "kbps", "mbps", "mbit",
# and "kbit" to mean (in this system) "kibps", "mibps", "mibit", and
# "kibit" and that if an older version is installed, all rates will
# be off by a small fraction.
suffixes = {
    "":         1,
    "bit":  1,
    "kibit":    1024,
    "kbit": 1000,
    "mibit":    1024*1024,
    "mbit": 1000000,
    "gibit":    1024*1024*1024,
    "gbit": 1000000000,
    "tibit":    1024*1024*1024*1024,
    "tbit": 1000000000000,
    "bps":  8,
    "kibps":    8*1024,
    "kbps": 8000,
    "mibps":    8*1024*1024,
    "mbps": 8000000,
    "gibps":    8*1024*1024*1024,
    "gbps": 8000000000,
    "tibps":    8*1024*1024*1024*1024,
    "tbps": 8000000000000
}

def get_tc_rate(s):
    """
    Parses an integer or a tc rate string (e.g., 1.5mbit) into bits/second
    """

    if type(s) == int:
        return s
    m = re.match(r"([0-9.]+)(\D*)", s)
    if m is None:
        return -1
    suffix = m.group(2).lower()
    if suffixes.has_key(suffix):
        return int(float(m.group(1)) * suffixes[suffix])
    else:
        return -1

def format_tc_rate(rate):
    """
    Formats a bits/second rate into a tc rate string
    """

    if rate >= 1000000000 and (rate % 1000000000) == 0:
        return "%.0fgbit" % (rate / 1000000000.)
    elif rate >= 1000000 and (rate % 1000000) == 0:
        return "%.0fmbit" % (rate / 1000000.)
    elif rate >= 1000:
        return "%.0fkbit" % (rate / 1000.)
    else:
        return "%.0fbit" % rate

def get_virt_ip(self, remote):
        link = self.get_link_id(remote)
        iface = self.get_iface_id(remote)
        first = link >> 6
        second = ((link & 0x3f)<<2) + iface
        return "192.168.%d.%d" % (first, second)

def get_virt_net(self, remote):
    link = self.get_link_id(remote)
    first = link >> 6
    second = (link & 0x3f)<<2
    return "192.168.%d.%d/30" % (first, second)

def get_topo_rspec(self, link):
    if link.end1 == self:
        remote = link.end2
    elif link.end2 == self:
        remote = link.end1
    else:
        raise Error("Link does not connect to Node")

    my_ip = self.get_virt_ip(remote)
    remote_ip = remote.get_virt_ip(self)
    net = self.get_virt_net(remote)
    bw = format_tc_rate(link.bps)
    ipaddr = remote.get_primary_iface().ipv4
    return (remote.id, ipaddr, bw, my_ip, remote_ip, net) 
