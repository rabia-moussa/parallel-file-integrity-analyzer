import hashlib as hs




def hashing(file):
    try :
        hashobj=hs.sha256()
        with open(file,'rb') as f:
                while True :
                    data=f.read(65000)
                    if not data : break
                    hashobj.update(data)
        hash=hashobj.hexdigest()
        if hash == None : raise Exception("Hashing failed")            
    except FileNotFoundError as err:
        print(f"Error occurred while hashing (file is not found){file}")
        return f"Error:{type(err).__name__}"    
    except PermissionError as err:
         print(f"Permission denied while hashing {file}")
         return f"Error:{type(err).__name__}"
    except OSError as err:
         print(f"OS error occurred while hashing {file} : {err} ")    
         return f"Error:{type(err).__name__}"
    except Exception as e:
             print(f"Error occurred while hashing {file} : {e}")
             return f"Error:{type(e).__name__}"
    else :
        # print(f"Hashing completed for {file}")
        return hash
        