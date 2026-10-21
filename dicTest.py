import os 
from hashingFile import hashing
import hashlib as hs
import time
import json
from osmod import parcour

path="/home/moussa/Documents"

for key,path in parcour(path).items():
    print(f"the path is {key} and the hash is {path} \n")




dictionary ={
    "/home/moussa/Documents/target.txt": 'hello',
    "/home/moussa/Documents/malw.py": "c9ae1d20c9ed7a92f0c11b3bb86acc5f",
    "/home/moussa/Documents/testFile.txt": 'hello',
    "/home/moussa/Documents/archive.tar": "58a72a6a60bb866a27e7354e068b15e8",
    "/home/moussa/Documents/osProject/hashingFile.py": "abebfada1367aa86923f2d9dac438af2",
    "/home/moussa/Documents/osProject/osmod.py": "b923204ab438a782ed8d7d186c3eb8e2",
    "/home/moussa/Documents/osProject/__pycache__/hashingFile.cpython-314.pyc": "d7d9f8e88435bbb19e28a6f5ab87a7d1",
    "/home/moussa/Documents/mosesFiles/hello": "7037af51d8767bcae37d10730fd6afc1",
    "/home/moussa/Documents/mosesFiles/progression.save.1": "9b83ca37d4bdf2155fb68e82f2ed7d76",
    "/home/moussa/Documents/mosesFiles/progression.save": "13015e20642119846125bf69a960715f",
    "/home/moussa/Documents/mosesFiles/progression": "9b312062c1987880065a0f2b7452adc4",
    "/home/moussa/Documents/otherFiles/other.txt": "894cb70424dd7704dd3e22de622ef243"
}

# def check_duplicate(hash_directory):
#     ls_duplicate=[]
#     for path , hash in hash_directory.items():
#         if hash_directory.values().count(hash) > 1 :
#             if path not in ls_duplicate: ls_duplicate.append(path)
#     return ls_duplicate  

# print(check_duplicate(dictionary))



