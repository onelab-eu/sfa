def import_manager(kind, type):
    """
    kind expected in ['registry', 'aggregate', 'slice', 'component']
    type is e.g. 'pl' or 'max' or whatever
    """
    basepath = 'sfa.managers'
    qualified = "%s.%s_manager_%s"%(basepath,kind,type)
    generic = "%s.%s_manager"%(basepath,kind)
    try: 
        manager = __import__(qualified, fromlist=[basepath])
    except:
        try:
            manager = __import__ (generic, fromlist=[basepath])
            if type != 'pl' : 
                logger.warn ("Using generic manager for %s with type=%s"%(kind,type))
        except:
            manager=None
    return manager
    
