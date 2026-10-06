import os

def loading_enviroment(filepath=".env"):
    """
    This function is to load .env variables, it ensures safety.


    """
    if not os.path.exists(filepath):
        return
    
    with open(filepath,"r",encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            
            key,value = line.split("=",1)
            value = value.strip().strip("\"'")
            os.environ[key.strip()] = value
            


