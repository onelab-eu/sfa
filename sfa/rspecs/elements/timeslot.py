###########################################################################
#    Copyright (C) 2012 by                                       
#    <savakian@sfa2.grenoble.senslab.info>                                                             
#
# Copyright: See COPYING file that comes with this distribution
#
###########################################################################
from sfa.rspecs.elements.element import Element

class Timeslot(Element):
    
    fields = [
        'date',
        'start_time',
        'timezone',
        'duration'
    ]        
