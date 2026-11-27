import multiprocessing
import threading as thread
import os
import time
import osmod
from hashingFile import hashing
import signal
import queue
import json
from stop_control import StopController


class MultiProcess(osmod.Sequential):
    def __init__(self, hash_db, worker_num , path , stop=None):
        if not isinstance(worker_num,int) or isinstance(worker_num,bool) or worker_num < 1 :
            raise ValueError(f'worker number must be an integer >= 1 , you put {worker_num} ' ) # P1-11 : maxsize=0 signifierait file illimitee + aucun consommateur
        super().__init__(hash_db, path)
        self.unprocessed=[]
        self.worker_num = worker_num
        self.queue = multiprocessing.Queue(maxsize=self.worker_num)
        self.results= multiprocessing.Queue(maxsize=self.worker_num)
        self.stop=stop or StopController('process') # the new hundler
        # P0-07 : evenement pose par le producteur quand il a fini d'emettre (apres les sentinelles)
        self.producer_done = multiprocessing.Event()
        # P0-06 : passe a True si un worker meurt sans envoyer sa sentinelle
        self.interrupted = False
        # self.flag=multiprocessing.Event() # by default is False

        self.isprocess=True # check weather is an process or not to take the decision about applying the SIG_IGN 
        # self.install_signal_handler()

    def producer(self): # fill the queue
        batch_size=64 
        batch=[]
        if self.isprocess:
            signal.signal(signal.SIGINT,signal.SIG_IGN) # ignore the interreption signal and keep working
        sttoped=False    
        try :    
            for root, dirs, files in os.walk(self.path):
                    if sttoped : break
                    if self.stop.abort_requested(): # if the flag is True wee stop the producer
                        break
                    for file in files:
                        # time.sleep(5)
                        if self.stop.abort_requested():
                            break
                        batch.append(os.path.join(root,file)) # append to a list a much way faster then put 
                        if len(batch) >= batch_size :
                         try :
                            self.queue.put(batch,timeout=20) # wee put all the list into the queue instead of doing this per file 
                         except queue.Full: # wait for 20 second if the put operation is failed then check if the queue is full (the workers probably dies) then break
                            sttoped=True
                            break
                         batch=[]
        finally :               
            if batch : # add the rest
                self.queue.put(batch)
                
                        # print(f"the process {os.getpid()} has put a value {os.path.join(root,file)} in the queue")
            for _ in range(self.worker_num): # indicates the end of the queue for each consumer (process)
                self.queue.put(None)      
            # P0-07 : previent les consommateurs que plus aucun lot ne viendra
            self.producer_done.set()

    def consumer(self): # assigned for each worker to get value from the queue
        batch=[]
        if self.isprocess: 
            signal.signal(signal.SIGINT,signal.SIG_IGN)
        # print(os.getpid , signal.getsignal(signal.SIGINT))
        try :
            while True:
                # if self.isprocess:
                #  signal.signal(signal.SIGINT,signal.SIG_IGN)
                try :
                 batch= self.queue.get(timeout=20)
                except queue.Empty: # wait for 20 second if the get operation is failed then check if the queue is still Empty (the workers probably dies) then continue
                    # P0-07 : file vide. Si le producteur a termine, on sort ; sinon on attend encore.
                    if self.producer_done.is_set():
                        break
                    continue  
                if batch is None:
                        break
                #   time.sleep(2)
                done,left=[] , []
                for i,path in enumerate(batch):
                    if self.stop.stop_requested():     # stop at the next file boundary
                     left = batch[i:]
                     break
                    
                    done.append((path,hashing(path)))
                if done:
                    self.results.put(("done",done))
                if left:
                    self.results.put(("left",left))    

                #   else :
                #       print(f"pid is [{os.getpid()}] batch complete {len(results)}/{len(batch)}", flush=True)
                


              # the function which will be used by the consumer will be called here      
            #   print(f"the process {os.getpid()} has taken a value {path} from the queue")
        finally :
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

    def collect_results(self, workers, producer_process=None):
        flag=0
        injected=False
        while flag < self.worker_num :
            try :
                item=self.results.get(timeout=1) # P0-06 : timeout pour ne pas bloquer a vie
            except queue.Empty:
                # P0-06 : plus aucun worker vivant -> des sentinelles manquent, le scan est incomplet
                if not any(worker.is_alive() for worker in workers):
                    print("workers died before sending all sentinels -> scan incomplete", flush=True)
                    self.interrupted=True
                    break
                # P0-07 : producteur mort SANS avoir pose producer_done (SIGKILL, exception, thread mort)
                #          -> personne n'enverra les sentinelles, on les injecte nous-memes.
                #          (test sur producer_done plutot que sur exitcode : un Thread n'a pas d'exitcode)
                if (producer_process is not None and not producer_process.is_alive()
                        and not self.producer_done.is_set() and not injected):
                    print("producer died -> injecting sentinels", flush=True)
                    self.interrupted=True # P0-06 : des fichiers n'ont peut-etre jamais ete admis
                    ok=True
                    for _ in range(self.worker_num):
                        try :
                            self.queue.put(None,timeout=1)
                        except queue.Full: # file pleine : on reessaiera au prochain tour
                            ok=False
                            break
                    injected=ok
                continue
            if item is None:
                flag+=1
                continue
            kind,payload=item
            if kind== "done":
                for path , info in payload :
                   self.hash_directory[path]=info
            else :
                self.unprocessed.extend(payload)  

            
     
    def parcour(self):
        self.hash_directory={}
        self.unprocessed=[]
        self.interrupted=False      # P0-06 : remis a zero pour chaque nouveau scan
        self.producer_done.clear()  # P0-07 : remis a zero pour chaque nouveau scan
        producer_process=self.start_producer()
        workers=self.start_workers()      
        self.collect_results(workers, producer_process) # P0-06/P0-07 : on passe les workers et le producteur
                  # the last thing I did "the problem wee want to fill the data into the correspondig strucutre which the func is called"
        producer_process.join(timeout=10)
        if producer_process.exitcode != 0:
            print("helper process failed, exitcode:", producer_process.exitcode)
        for worker in workers:
             worker.join()
             if worker.exitcode != 0:
              print("helper process failed, exitcode:", worker.exitcode)
             
        # print(producer_process.exitcode()) # if it prints 0 the producer is ends otherwise there is a problem      
        return self.hash_directory 

         
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
            if  self.stop.abort_requested():
                return
            self.First_run() # create a baseline
            i=0
            while True:
                if  self.stop.abort_requested():
                    break
                i+=1
                self.run() # return the modified, new, deleted and duplicates files
                if self.stop.abort_requested():
                        break
                with open(self.hash_db,'w') as f:
                    json.dump(self.hash_directory, f) # print the hash directory in the json file (put the new version as the recent one)
                if self.unprocessed : print("unprocessed files: ",self.unprocessed)
                print("the timestamp end",i)
                if self.stop.wait_abort_requested(timestamp): # waits for the signal to be set by the main process 
                    break

                


    
if __name__ == "__main__" :
    mlt=MultiProcess("hash_database.json",3,'/home/moussa/Documents/otherFiles')
    mlt.verification_tmp(10)
    # # time.sleep(30)
    # # print("the timestamp end")
    # def handler(signal , frame):
    #      mlt.hundler()

    # signal.signal(signal.SIGINT,handler)
    # # multiprocessing.set_start_method("fork",force=True)
    # # mlt.run()
    