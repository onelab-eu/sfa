# sfa should not depend on sfatables
# if the sfatables.runtime import fails, just define run_sfatables as identity

try:
    from sfatables.runtime import SFATablesRules

    def fetch_context(slice_hrn, user_hrn, contexts):
        """
        Returns the request context required by sfatables. At some point, this
        mechanism should be changed to refer to "contexts", which is the
        information that sfatables is requesting. But for now, we just return
        the basic information needed in a dict.
        """
        base_context = {'sfa':{'user':{'hrn':user_hrn}, 'slice':{'hrn':slice_hrn}}}
        return base_context

    def run_sfatables(chain, hrn, origin_hrn, rspec, context_callback = None ):
        """
        Run the rspec through sfatables
        @param chain Name of rule chain
        @param hrn Object's hrn
        @param origin_hrn Original caller's hrn
        @param rspec Incoming rspec
        @param context_callback Callback used to generate the request context  
        
        @return rspec
        """
        if not context_callback:
            context_callback = fetch_context

        chain = chain.upper()
        rules = SFATablesRules(chain)
        if rules.sorted_rule_list:
            contexts = rules.contexts
            request_context = context_callback(hrn, origin_hrn, contexts)
            rules.set_context(request_context)
            newrspec = rules.apply(rspec)
        else:
            newrspec = rspec
        return newrspec

except:
    
    from sfa.util.logging import logger
    def run_sfatables (_,__,___, rspec, ____=None):
        logger.warning("Cannot import sfatables.runtime, please install package sfa-sfatables")
        return rspec
