# yet another way to display records...
def beginning (foo,size=15):
    full="%s"%foo
    if len(full)<=size: return full
    return full[:size-3]+'...'

def printable (record_s):
    # a list of records :
    if isinstance (record_s,list):
        return "[" + "\n".join( [ printable(r) for r in record_s ]) + "]"
    if isinstance (record_s, dict):
        return "{" + " , ".join( [ "%s:%s"%(k,beginning(v)) for k,v in record_s.iteritems() ] ) + "}"
    if isinstance (record_s, str):
        return record_s
    return "unprintable [[%s]]"%record_s
