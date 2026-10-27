import multiprocessing
import os
import osmod
from hashingFile import hashing
import time

class MultiProcess(osmod.Sequential):
    def __init__(self, hash_db, worker_num , path):
        super().__init__(hash_db, path)
        self.worker_num = worker_num
        self.queue = multiprocessing.Queue(maxsize=3)
        self.results= multiprocessing.Queue(maxsize=3)

    def producer(self): # fill the queue
        for root, dirs, files in os.walk(self.path):
                for file in files:
                    self.queue.put(os.path.join(root,file))
                    # print(f"the process {os.getpid()} has put a value {os.path.join(root,file)} in the queue")
        for _ in range(self.worker_num): # indicates the end of the queue for each consumer (process)
             self.queue.put(None)        

    def consumer(self): # assigned for each worker to get value from the queue
        while True:
              
              path= self.queue.get()
              if path is None:
                    break
            #   time.sleep(10)
              self.results.put((path,hashing(path)))
              # the function which will be used by the consumer will be called here      
            #   print(f"the process {os.getpid()} has taken a value {path} from the queue")
        self.results.put(None)

    def parcour(self):
        self.hash_directory={}
        producer_process=multiprocessing.Process(target=self.producer)
        workers=[multiprocessing.Process(
                target=self.consumer,
                 # consumer requires a func argument
                name=f"process_{i}",
            ) for i in range(self.worker_num)]   
         
        producer_process.start()
        for worker in workers :
             worker.start()

        flag=0
        while flag < self.worker_num :
             item=self.results.get()
             if item==None:
                  flag+=1
             else : 
                  path , info = item
                  self.hash_directory[path]=info
                  

                  # the last thing I did "the problem wee want to fill the data into the correspondig strucutre which the func is called"
        producer_process.join()
        for worker in workers:
             worker.join()
        return self.hash_directory 

if __name__ == "__main__" :
    mlt=MultiProcess("hash_database.json",3,'/home/moussa/Documents/otherFiles')
    # mlt.First_run()
    # time.sleep(30)
    # print("the timestamp end")

    print('the check run is now starting')
    modified, new, deleted ,duplicates = mlt.check_run()
    print('the modified files are: ', modified)
    print('the new files are: ', new)
    print('the deleted files are: ', deleted)
    print('the duplicate files are: ', duplicates)

     
    pass  

           
              
              
         
   
