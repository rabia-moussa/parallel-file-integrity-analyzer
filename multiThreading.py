import signal 
import threading as thread
import time 
import osmod
import multiProcess
from queue import Queue
from stop_control import StopController

class MultiTreaded(multiProcess.MultiProcess):
    def __init__(self,hash_db,worker_num,path):
        super().__init__(hash_db,worker_num,path,StopController('thread'))
        self.queue=Queue(maxsize=worker_num)
        self.results=Queue(maxsize=worker_num)
        self.isprocess=False # check weather is an process or not to take the decision about applying the SIG_IGN

    def parcour(self):
        self.hash_directory={}
        producer_process=thread.Thread(target=self.producer)
        producer_process
        workers=[thread.Thread(
                target=self.consumer,
                 # consumer requires a func argument
                name=f"thread_{i}",
            ) for i in range(self.worker_num)]   
         
        producer_process.start()
        for worker in workers :
             worker.start()

        # flag=0
        # while flag < self.worker_num :
        #      item=self.results.get()
        #      if item is None:
        #           flag+=1
        #      else : 
        #         for path , info in item :
        #           self.hash_directory[path]=info
        self.collect_results()          
                  

                  # the last thing I did "the problem wee want to fill the data into the correspondig strucutre which the func is called"
        producer_process.join()
        for worker in workers:
             worker.join()
        return self.hash_directory   
    

    
if __name__ == "__main__" :
    multiT=MultiTreaded("hash_database.json",3,'/home/moussa/Documents')
    multiT.verification_tmp(5)
    
    # # time.sleep(10)
    # print('the check run is now starting')
    # def handler(signal , frame):
    #          multiT.hundler()

    # signal.signal(signal.SIGINT,handler)
    
    # multiT.First_run()
    
    # print('the real  check run is now starting')
    # # time.sleep(20)
   
    # modified, new, deleted ,duplicates = multiT.check_run()
    # print('the modified files are: ', modified)
    # print('the new files are: ', new)
    # print('the deleted files are: ', deleted)
    # print('the duplicate files are: ', duplicates)
    
     
 

# def square(n):
#     print(thread.current_thread())
#     print(thread.get_ident())

# t1=thread.Thread(target= square,name="thread number one " ,args= (2,))
# t2=thread.Thread(target=square, name="thread number two" , args=(4,))

# t1.start()
# t2.start()

# print(t1.name)
# print(t2.name)
# print(t1.is_alive())
# print(thread.active_count())

# t1.join()
# t2.join()

# thread.main_thread