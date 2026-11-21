import multiprocessing
import threading as thread
import os
import time
import osmod
from hashingFile import hashing
import signal
import json


class MultiProcess(osmod.Sequential):
    def __init__(self, hash_db, worker_num , path):
        super().__init__(hash_db, path)
        self.worker_num = worker_num
        self.queue = multiprocessing.Queue(maxsize=3)
        self.results= multiprocessing.Queue(maxsize=3)
        self.flag=multiprocessing.Event() # by default is False
        self.isprocess=True # check weather is an process or not to take the decision about applying the SIG_IGN 
        self.install_signal_handler()

    def producer(self): # fill the queue
        batch_size=64
        batch=[]
        if self.isprocess:
            signal.signal(signal.SIGINT,signal.SIG_IGN) # ignore the interreption signal and keep working
            
        for root, dirs, files in os.walk(self.path):
                if self.flag.is_set(): # if the flag is True wee stop the producer
                     break
                for file in files:
                    if self.flag.is_set():
                        break
                    batch.append(os.path.join(root,file)) # append to a list a much way faster then put 
                    if len(batch) >= batch_size :    
                       self.queue.put(batch) # wee put all the list into the queue instead of doing this per file
                       batch=[]
        if batch : # add the rest
            self.queue.put(batch)
             
                    # print(f"the process {os.getpid()} has put a value {os.path.join(root,file)} in the queue")
        for _ in range(self.worker_num): # indicates the end of the queue for each consumer (process)
             self.queue.put(None)      

    def consumer(self): # assigned for each worker to get value from the queue
        batch=[]
        if self.isprocess: 
            signal.signal(signal.SIGINT,signal.SIG_IGN)
        # print(os.getpid , signal.getsignal(signal.SIGINT))
        while True:
              if self.isprocess:
               signal.signal(signal.SIGINT,signal.SIG_IGN)
              batch= self.queue.get()
              if batch is None:
                    break
            #   time.sleep(2)
              results=[]
              for path in batch:
                if self.flag.is_set():      # stop at the next file boundary
                 break
                results.append((path,hashing(path)))
            #   else :
            #       print(f"pid is [{os.getpid()}] batch complete {len(results)}/{len(batch)}", flush=True)
              if results:
               self.results.put(results)


              # the function which will be used by the consumer will be called here      
            #   print(f"the process {os.getpid()} has taken a value {path} from the queue")
        self.results.put(None)

    def start_producer(self):
        producer_process = multiprocessing.Process(target=self.producer)
        producer_process.start()
        return producer_process


    def start_workers(self):
        workers= [multiprocessing.Process(
            target=self.consumer,
            name=f"process_{i}",
            ) for i in range(self.worker_num)]
        
        for worker in workers :
            worker.start()
        return workers

    def collect_results(self):
        flag=0
        while flag < self.worker_num :
            item=self.results.get()
            if item is None:
                flag+=1
            else : 
                for path , info in item :
                 self.hash_directory[path]=info

            
     
    def parcour(self):
        self.hash_directory={}
        producer_process=self.start_producer()
        workers=self.start_workers()      
        self.collect_results()
                  # the last thing I did "the problem wee want to fill the data into the correspondig strucutre which the func is called"
        producer_process.join()
        for worker in workers:
             worker.join()
        # print(producer_process.exitcode()) # if it prints 0 the producer is ends otherwise there is a problem      
        return self.hash_directory 

    def hundler(self):
         """made to hundle the gracefull stopage"""
         self.flag.set()
         
    def verification_tmp(self, timestamp):
        if not self.isprocess:
            return self.helper(timestamp)        
        helper_p = multiprocessing.Process(target=self.helper, args=(timestamp,))
        helper_p.start()
        helper_p.join()
        if helper_p.exitcode != 0:
            print("helper process failed, exitcode:", helper_p.exitcode)

           
            
    def helper(self,timestamp):
            if self.isprocess:
                signal.signal(signal.SIGINT,signal.SIG_IGN)
            if self.flag.is_set():
                return
            self.First_run() # create a baseline
            i=0
            while True:
                if self.flag.is_set():
                    break
                i+=1
                self.run() # return the modified, new, deleted and duplicates files
                if self.flag.is_set():
                        break
                with open(self.hash_db,'w') as f:
                    json.dump(self.hash_directory, f) # print the hash directory in the json file (put the new version as the recent one)
                print("the timestamp end",i)
                if self.flag.wait(timestamp): # waits for the signal to be set by the main process 
                    break

                

    def install_signal_handler(self):
        if thread.current_thread() is thread.main_thread():
            signal.signal(signal.SIGINT, self.handler_sigint)

    def handler_sigint(self, signal , frame):
         self.hundler()     

    
if __name__ == "__main__" :
    mlt=MultiProcess("hash_database.json",3,'/home/moussa/')
    mlt.verification_tmp(10)
    # # time.sleep(30)
    # # print("the timestamp end")
    # def handler(signal , frame):
    #      mlt.hundler()

    # signal.signal(signal.SIGINT,handler)
    # # multiprocessing.set_start_method("fork",force=True)
    # # mlt.run()
    