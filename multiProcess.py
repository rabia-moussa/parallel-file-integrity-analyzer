import multiprocessing
import os
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

    def producer(self): # fill the queue
        if self.isprocess:
            signal.signal(signal.SIGINT,signal.SIG_IGN) # ignore the interreption signal and keep working
        for root, dirs, files in os.walk(self.path):
                if self.flag.is_set(): # if the flag is True wee stop the producer
                     break
                for file in files:
                    if self.flag.is_set():
                        break
                    self.queue.put(os.path.join(root,file))
                    # print(f"the process {os.getpid()} has put a value {os.path.join(root,file)} in the queue")
        for _ in range(self.worker_num): # indicates the end of the queue for each consumer (process)
             self.queue.put(None)      

    def consumer(self): # assigned for each worker to get value from the queue
        if self.isprocess: 
            signal.signal(signal.SIGINT,signal.SIG_IGN)
        # print(os.getpid , signal.getsignal(signal.SIGINT))
        while True:
              if self.isprocess:
               signal.signal(signal.SIGINT,signal.SIG_IGN)
              path= self.queue.get()
              if path is None:
                    break
            #   time.sleep(2)
              self.results.put((path,hashing(path)))
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
            if item==None:
                flag+=1
            else : 
                path , info = item
                print(f"the process {os.getpid()} had this result {path} and the hash {info}")
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

    def verification_tmp(self,timestamp):
            self.First_run() # create a baseline
            i=0
            while True:
                if self.flag.is_set():
                    break
                i+=1
                self.run() # return the modified, new, deleted and duplicates files
                with open(self.hash_db,'w') as f:
                    json.dump(self.hash_directory, f) # print the hash directory in the json file (put the new version as the recent one)
                print("the timestamp end",i)
                if self.flag.wait(timestamp):
                    break

    
if __name__ == "__main__" :
    mlt=MultiProcess("hash_database.json",3,'/home/moussa/Documents/otherFiles')
    
    # time.sleep(30)
    # print("the timestamp end")
    def handler(signal , frame):
         mlt.hundler()

    signal.signal(signal.SIGINT,handler)
    # multiprocessing.set_start_method("fork",force=True)
    # mlt.run()
    mlt.verification_tmp(5)
    
     
      

           
              
              
         
   
