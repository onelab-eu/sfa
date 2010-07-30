import threading
import time
from Queue import Queue

def ThreadedMethod(callable, queue):
    """
    A function decorator that returns a running thread. The thread
    runs the specified callable and stores the result in the specified
    results queue
    """
    def wrapper(args, kwds):
        class ThreadInstance(threading.Thread): 
            def run(self):
                try:
                    queue.put(callable(*args, **kwds))
                except:
                    # ignore errors
                    pass
        thread = ThreadInstance()
        thread.start()
        return thread
    return wrapper

 

class ThreadManager:
    """
    ThreadManager executes a callable in a thread and stores the result
    in a thread safe queue. 
    """
    queue = Queue()
    threads = []

    def run (self, method, *args, **kwds):
        """
        Execute a callable in a separate thread.    
        """
        method = ThreadedMethod(method, self.queue)
        thread = method(args, kwds)
        self.threads.append(thread)

    start = run

    def get_results(self):
        """
        Return a list of all the results so far. Blocks until 
        all threads are finished. 
        """
        for thread in self.threads:
            thread.join()
        results = []
        while not self.queue.empty():
            results.append(self.queue.get())  
        return results
           
if __name__ == '__main__':

    def f(name, n, sleep=1):
        nums = []
        for i in range(n, n+5):
            print "%s: %s" % (name, i)
            nums.append(i)
            time.sleep(sleep)
        return nums

    threads = ThreadManager()
    threads.run(f, "Thread1", 10, 2)
    threads.run(f, "Thread2", -10, 1)

    results = threads.get_results()
    print "Results:", results
