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
