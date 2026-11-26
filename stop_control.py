import signal
import threading as thread 
import multiprocessing
import threading
import time

class StopController:
    """gracefull stoppage
    2 modes :
    first ctrl + c -> stop : producer stop and the workers drains the queue
    second ctrl +c -> abort : workers stopped when they want to start processing the next file 
    """
    def __init__(self , ctx=None):
     self.mode = ctx
     self.event = multiprocessing.Event() if ctx == 'process' else threading.Event()
     self.abort = multiprocessing.Event() if ctx == 'process' else threading.Event()
     self.clicks=0
     self.install_signal_handler()



    def stopage(self,signal , frame):
       self.clicks+=1
       if self.clicks==1:
        self.abort.set()
       if self.clicks==2:
        self.event.set() 

    
    def install_signal_handler(self):
        if thread.current_thread() is thread.main_thread():
            signal.signal(signal.SIGINT, self.stopage)   

    def stop_requested(self):
       return self.event.is_set()
    
    def abort_requested(self):
       return self.abort.is_set()

    def wait_requested(self,timestamp):
       self.event.wait(timestamp)
    
    def wait_abort_requested(self,timestamp):
       self.abort.wait(timestamp)   