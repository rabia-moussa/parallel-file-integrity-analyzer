import hashlib as hs




def hashing(file):
    try :
        hashobj=hs.md5()
        with open(file,'rb') as f:
                while True :
                    data=f.read(65000)
                    if not data : break
                    hashobj.update(data)
        hash=hashobj.hexdigest()
        if hash == None : raise Exception("Hashing failed")            
    except FileNotFoundError:
        print(f"Error occurred while hashing (file is not found){file}")    
    except PermissionError:
         print(f"Permission denied while hashing {file}")
    except OSError as err:
         print(f"OS error occurred while hashing {file} : {err} ")    
    except Exception as e:
             print(f"Error occurred while hashing {file} : {e}")
    else :
        # print(f"Hashing completed for {file}")
        return hash
        