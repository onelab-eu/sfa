from sfa.util.sfalogging import logger

def import_manager(kind, type):
    """
    kind expected in ['registry', 'aggregate', 'slice', 'component']
    type is e.g. 'pl' or 'max' or whatever
    """
    basepath = 'sfa.managers'
    qualified = "%s.%s_manager_%s"%(basepath,kind,type)
    generic = "%s.%s_manager"%(basepath,kind)

    message="import_manager for kind=%s and type=%s"%(kind,type)
    try: 
        manager = __import__(qualified, fromlist=[basepath])
        logger.info ("%s: loaded %s"%(message,qualified))
    except:
        try:
            manager = __import__ (generic, fromlist=[basepath])
            if type != 'pl' : 
                logger.warn ("%s: using generic with type!='pl'"%(message))
            logger.info("%s: loaded %s"%(message,generic))
        except:
            manager=None
            logger.log_exc("%s: unable to import either %s or %s"%(message,qualified,generic))
    return manager
    
