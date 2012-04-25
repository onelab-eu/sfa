from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.timeslot import Timeslot
import sys

class Slabv1Timeslot :
    @staticmethod 
    def get_slice_timeslot(xml, filter={}):
        print>>sys.stderr, "\r\n \r\n \t\t \t SLABV1TIMESLOT.pY >>>>>>>>>>>>>>>>>>>>>>>>>>>>> \t  get_slice_timeslot  "
        xpath = '//default:timeslot | //timeslot' 
        timeslot_elems = xml.xpath(xpath)  
        print>>sys.stderr, "\r\n \r\n \t\t \t SLABV1TIMESLOT.pY >>>>>>>>>>>>>>>>>>>>>>>>>>>>> \t  get_slice_timeslot    timeslot_elems %s"%(timeslot_elems)
        for timeslot_elem in timeslot_elems:  
            timeslot = Timeslot(timeslot_elem.attrib, timeslot_elem) 
            print>>sys.stderr, "\r\n \r\n \t\t \t SLABV1TIMESLOT.pY >>>>>>>>>>>>>>>>>>>>>>>>>>>>> \t  get_slice_timeslot   timeslot  %s"%(timeslot)

        return timeslot