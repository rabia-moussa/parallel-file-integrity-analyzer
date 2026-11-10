from collections import Counter
import os 
from hashingFile import hashing
import hashlib as hs

import json

import time

class Sequential:
    def __init__(self, hash_db, path):
        self.hash_db = hash_db
        self.path = path
        self.hash_directory = {}

    
    def check_duplicate(self):
        valid_files={}
        for path , hash in self.hash_directory.items():
            if hash == None : continue
            try :
                if  os.path.getsize(path) == 0 :
                    continue
            except OSError as err:
                print(f"OS error occurred while checking duplicates for {path} : {err} ")
                continue    
            valid_files[path]=hash
        hash_counts = Counter(valid_files.values())
        # print(hash_counts.elements())
        # print(list(hash_counts.elements()))
        return [
                path for path , hash in valid_files.items() if hash_counts[hash] > 1] # I must resturn a tuple contain all duplicated files in the same group 
            # if list(hash_directory.values()).count(hash) > 1 :
            #     if path not in ls_duplicate: ls_duplicate.append(path)
            
                
                
    def check_modified(self):
        ls_modified=[]
        ls_new=[]
        ls_deleted=[]
        with open(self.hash_db ,'r') as f:
            hash_database=json.load(f)
            print(f"the hash database is {hash_database}")
            print(f"the hash directory is {self.hash_directory}")
            ls_modified=[path for path , hash in self.hash_directory.items()  if path in hash_database and hash != hash_database[path]]
            ls_new=[path for path in self.hash_directory if path not in hash_database]
            ls_deleted=[path for path in hash_database if path not in self.hash_directory and  not os.path.lexists(path)] # check if the file is deleted in the current run and in the disk
        return ls_modified, ls_new, ls_deleted

   

    def parcour(self):
        print("now using the walk command")
        self.hash_directory={}
        for root, dirs, files in os.walk(self.path):   
            for name in files:
                # print(name , "the permissions are: ", oct(os.stat(os.path.join(root, name)).st_mode)[-3:])
                # print(f"the path is {os.path.join(root,name)} and the hash is {hashing(os.path.join(root,name))} \n")
                self.hash_directory[os.path.join(root,name)]=hashing(os.path.join(root,name))
        return self.hash_directory  
          


    def First_run(self):
        with open(self.hash_db,'w') as f:
            json.dump(self.parcour(), f)


    def check_run(self):
        self.hash_directory=self.parcour()
        modified, new, deleted = self.check_modified()
        duplicates = self.check_duplicate()
        return modified, new, deleted, duplicates

    def run(self):
        print('the check run is now starting')
        modified, new, deleted ,duplicates = self.check_run()
        print('the modified files are: ', modified)
        print('the new files are: ', new)
        print('the deleted files are: ', deleted)
        print('the duplicate files are: ', duplicates)
     
    def verification_tmp(self,timestamp):
            self.First_run() # create a baseline
            i=0
            while True:
                i+=1
                self.run() # return the modified, new, deleted and duplicates files
                with open(self.hash_db,'w') as f:
                    json.dump(self.hash_directory, f) # print the hash directory in the json file (put the new version as the recent one)
                print("the timestamp end",i)
                time.sleep(timestamp)
    
if __name__ =="__main__":
    seq = Sequential('hash_database.json', '/home/moussa/Documents/otherFiles')
    seq.verification_tmp(5)    



    # print('the first run is now starting')
    # seq = Sequential('hash_database.json', '/home/moussa/Documents/otherFiles')
    # seq.First_run()
    
    # time.sleep(30)
    # print("the timestamp end")

    # print('the check run is now starting')
    # modified, new, deleted ,duplicates = seq.check_run()

    # print('the modified files are: ', modified)
    # print('the new files are: ', new)
    # print('the deleted files are: ', deleted)
    # print('the duplicate files are: ', duplicates)



 
# print(check_duplicate(parcour('/home/moussa/Documents')))

                    


# next steps 
# 1- replace the brut path by a variable that can be passed as an argument to the script  
# 2 - save the hashing result in a json format (dictionanry before) with the file path as key and the hash as value
# 3- add a duplicate detection function that will check if the hash already exists 
# 4- the results of errors/modified files + duplicates should be saved in a log file with the date and time of the run