from collections import Counter
import os 
from hashingFile import hashing
import hashlib as hs

import json

import time

def check_duplicate(hash_directory):
    valid_files={}
    for path , hash in hash_directory.items():
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
            path for path , hash in valid_files.items() if hash_counts[hash] > 1]
        # if list(hash_directory.values()).count(hash) > 1 :
        #     if path not in ls_duplicate: ls_duplicate.append(path)
         
            
            
def check_modified(hash_directory, hash_database):
    ls_modified=[]
    ls_new=[]
    ls_deleted=[]
    with open(hash_database ,'r') as f:
        hash_database=json.load(f)
        ls_modified=[path for path , hash in hash_directory.items()  if path in hash_database and hash != hash_database[path]]
        ls_new=[path for path in hash_directory if path not in hash_database]
        ls_deleted=[path for path in hash_database if path not in hash_directory]  
    return ls_modified, ls_new, ls_deleted



def parcour(path):
    print("now using the walk command")
    hash_directory={}
    for root, dirs, files in os.walk(path):   
        for name in files:
            # print(name , "the permissions are: ", oct(os.stat(os.path.join(root, name)).st_mode)[-3:])
            # print(f"the path is {os.path.join(root,name)} and the hash is {hashing(os.path.join(root,name))} \n")
            hash_directory[os.path.join(root,name)]=hashing(os.path.join(root,name))
    return hash_directory        


def First_run(path, hash_database):
    with open(hash_database,'w') as f:
        json.dump(parcour(path), f)


def check_run(path , hash_database):
    hash_directory=parcour(path)
    modified, new, deleted = check_modified(hash_directory, hash_database)
    duplicates = check_duplicate(hash_directory)
    return modified, new, deleted, duplicates



print('the first run is now starting')
First_run('/home/moussa/Documents', 'hash_database.json')

time.sleep(120)

print('the check run is now starting')
modified, new, deleted ,duplicates = check_run('/home/moussa/Documents', 'hash_database.json')

print('the modified files are: ', modified)
print('the new files are: ', new)
print('the deleted files are: ', deleted)
print('the duplicate files are: ', duplicates)



 
# print(check_duplicate(parcour('/home/moussa/Documents')))

                    


# next steps 
# 1- replace the brut path by a variable that can be passed as an argument to the script  
# 2 - save the hashing result in a json format (dictionanry before) with the file path as key and the hash as value
# 3- add a duplicate detection function that will check if the hash already exists 
# 4- the results of errors/modified files + duplicates should be saved in a log file with the date and time of the run