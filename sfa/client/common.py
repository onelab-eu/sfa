# a few utilities common to sfi and sfaadmin

def optparse_listvalue_callback(option, opt, value, parser):
    former=getattr(parser.values,option.dest)
    if not former: former=[]
    # support for using e.g. sfi update -t slice -x the.slice.hrn -r none
    # instead of -r '' which is painful and does not pass well through ssh
    if value.lower()=='none':
        newvalue=former
    else:
        newvalue=former+value.split(',')
    setattr(parser.values, option.dest, newvalue)

def optparse_dictvalue_callback (option, option_string, value, parser):
    try:
        (k,v)=value.split('=',1)
        d=getattr(parser.values, option.dest)
        d[k]=v
    except:
        parser.print_help()
        sys.exit(1)

# a code fragment that could be helpful for argparse which unfortunately is 
# available with 2.7 only, so this feels like too strong a requirement for the client side
#class ExtraArgAction  (argparse.Action):
#    def __call__ (self, parser, namespace, values, option_string=None):
# would need a try/except of course
#        (k,v)=values.split('=')
#        d=getattr(namespace,self.dest)
#        d[k]=v
#####
#parser.add_argument ("-X","--extra",dest='extras', default={}, action=ExtraArgAction,
#                     help="set extra flags, testbed dependent, e.g. --extra enabled=true")
    
##############################
# these are not needed from the outside
def terminal_render_plural (how_many, name,names=None):
    if not names: names="%ss"%name
    if how_many<=0: return "No %s"%name
    elif how_many==1: return "1 %s"%name
    else: return "%d %s"%(how_many,names)

def terminal_render_default (record,options):
    print "%s (%s)" % (record['hrn'], record['type'])
def terminal_render_user (record, options):
    print "%s (User)"%record['hrn'],
    if record.get('reg-pi-authorities',None): print " [PI at %s]"%(" and ".join(record['reg-pi-authorities'])),
    if record.get('reg-slices',None): print " [IN slices %s]"%(" and ".join(record['reg-slices'])),
    user_keys=record.get('reg-keys',[])
    if not options.verbose:
        print " [has %s]"%(terminal_render_plural(len(user_keys),"key"))
    else:
        print ""
        for key in user_keys: print 8*' ',key.strip("\n")
        
def terminal_render_slice (record, options):
    print "%s (Slice)"%record['hrn'],
    if record.get('reg-researchers',None): print " [USERS %s]"%(" and ".join(record['reg-researchers'])),
#    print record.keys()
    print ""
def terminal_render_authority (record, options):
    print "%s (Authority)"%record['hrn'],
    if record.get('reg-pis',None): print " [PIS %s]"%(" and ".join(record['reg-pis'])),
    print ""
def terminal_render_node (record, options):
    print "%s (Node)"%record['hrn']


### used in sfi list
def terminal_render (records,options):
    # sort records by type
    grouped_by_type={}
    for record in records:
        type=record['type']
        if type not in grouped_by_type: grouped_by_type[type]=[]
        grouped_by_type[type].append(record)
    group_types=grouped_by_type.keys()
    group_types.sort()
    for type in group_types:
        group=grouped_by_type[type]
#        print 20 * '-', type
        try:    renderer=eval('terminal_render_'+type)
        except: renderer=terminal_render_default
        for record in group: renderer(record,options)


####################
def filter_records(type, records):
    filtered_records = []
    for record in records:
        if (record['type'] == type) or (type == "all"):
            filtered_records.append(record)
    return filtered_records


