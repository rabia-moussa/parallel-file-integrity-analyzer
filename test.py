import time
import multiprocessing
import os
# q =Queue(maxsize=3)


# print("inital size: ",q.qsize())


# q.put("etudiant1")
# q.put("etudiant2")
# q.put("etudiant3")
# print(q.empty())


# print(q.get(timeout=10))
# print(q.get(timeout=10))
# print(q.get(timeout=10))
# print(q.get(timeout=10))
# # q.get(timeout=10)
# print(q.qsize())
path=["path1","path2","path3","path4", "path5","path6","path7"]


que=multiprocessing.Queue(maxsize=3)




def producer(q,ls): # fill the queue
        for elm in ls:
             q.put(elm)
             print(f"the process {os.getpid()} has put a value {elm} to the queue")
        for _ in range(2):
            q.put(None)    


       
       




def consumer(q): # assinged for each worker to get a value from the queue
    while True:
        y=q.get()        
        print(f"the process {os.getpid()} has take a value {y} from the queue")
        # time.sleep(5)
        if y is None : break
   




if __name__== "__main__":
   


    process1=multiprocessing.Process(target=consumer , args=(que,))
    process3=multiprocessing.Process(target=consumer , args=(que,))


    process2=multiprocessing.Process(target=producer , args=(que,path,))


    workers=[process1,process3]
    process2.start()
    for prs in workers:
        prs.start()
    for prs in workers:
         prs.join()    


   


   
    # process1.start()
    # process1.join()
   


    # print(que.full())
    # process1.start()
    # process1.join()
   
    # process1.start()
    # process1.join()
   
   
   
   


    # ls=[1,2,3]
    # process1=multiprocessing.Process(target=worker , args=(ls,))
    # process2=multiprocessing.Process(target=worker , args=(10,))
   


    # print(f"the result in view of the main process {result} ")

