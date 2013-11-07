import threading
import traceback
import time
from Queue import Queue
from sfa.util.sfalogging import logger

def ThreadedMethod(callable, results, errors):
    """
    A function decorator that returns a running thread. The thread
    runs the specified callable and stores the result in the specified
    results queue
    """
    def wrapper(args, kwds):
        class ThreadInstance(threading.Thread): 
            def run(self):
                try:
                    results.put(callable(*args, **kwds))
                except Exception, e:
                    logger.log_exc('MultiClient: Error in thread: ')
                    errors.put(traceback.format_exc())
                    
        thread = ThreadInstance()
        thread.start()
        return thread
    return wrapper

 

class MultiClient:
    """
    MultiClient allows to issue several SFA calls in parallel in different threads
    and stores the results in a thread safe queue. 
    """

    def __init__(self):
        self.results = Queue()
        self.errors = Queue()
        self.threads = []

    def run (self, method, *args, **kwds):
        """
        Execute a callable in a separate thread.    
        """
        method = ThreadedMethod(method, self.results, self.errors)
        thread = method(args, kwds)
        self.threads.append(thread)

    start = run

    def join(self):
        """
        Wait for all threads to complete  
        """
        for thread in self.threads:
            thread.join()

    def get_results(self, lenient=True):
        """
        Return a list of all the results so far. Blocks until 
        all threads are finished. 
        If lenient is set to false the error queue will be checked before 
        the response is returned. If there are errors in the queue an SFA Fault will 
        be raised.   
        """
        self.join()
        results = []
        if not lenient:
            errors = self.get_errors()
            if errors: 
                raise Exception(errors[0])

        while not self.results.empty():
            results.append(self.results.get())  
        return results

    def get_errors(self):
        """
        Return a list of all errors. Blocks untill all threads are finished
        """
        self.join()
        errors = []
        while not self.errors.empty():
            errors.append(self.errors.get())
        return errors

    def get_return_value(self):
        """
        Get the value that should be returuned to the client. If there are errors then the
        first error is returned. If there are no errors, then the first result is returned  
        """
    
           
if __name__ == '__main__':

    def f(name, n, sleep=1):
        nums = []
        for i in range(n, n+5):
            print "%s: %s" % (name, i)
            nums.append(i)
            time.sleep(sleep)
        return nums
    def e(name, n, sleep=1):
        nums = []
        for i in range(n, n+3) + ['n', 'b']:
            print "%s: 1 + %s:" % (name, i)
            nums.append(i + 1)
            time.sleep(sleep)
        return nums      

    threads = MultiClient()
    threads.run(f, "Thread1", 10, 2)
    threads.run(f, "Thread2", -10, 1)
    threads.run(e, "Thread3", 19, 1)

    #results = threads.get_results()
    #errors = threads.get_errors()
    #print "Results:", results
    #print "Errors:", errors
    results_xlenient = threads.get_results(lenient=False)

