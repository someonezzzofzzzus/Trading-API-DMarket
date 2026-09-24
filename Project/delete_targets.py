import os,sys,time,requests,json

from datetime import datetime

from nacl.bindings import crypto_sign  
"""
    Script requests active targets of the user from Dmarket server and sends POST request to delete them all
"""
# Make the shared credentials loader importable regardless of working directory.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import credentials

# ---------------------------------------------------------------

public_key, secret_key = credentials.load_api_keys()


# ---------------------------------------------------------------


def encryption_get(pKey,sKey,url):
    
    # ---------------------------------------------------------------
    nonce = str(round(datetime.now().timestamp()))  
    api_url_path = url

    #Encryption process for reqests
    method = "GET"
    string_to_sign = method + api_url_path + nonce
    signature_prefix = "dmar ed25519 "
    encoded = string_to_sign.encode('utf-8')
    signature_bytes = crypto_sign(encoded, bytes.fromhex(sKey))
    signature = signature_bytes[:64].hex()
    headers = {
        "X-Api-Key": pKey,
        "X-Request-Sign": signature_prefix + signature,
        "X-Sign-Date": nonce
    }
    
    return headers
    #-------------------------------------------------------------------

def encryption_post(body,pKey,sKey,url):   
     
    nonce = str(round(datetime.now().timestamp()))
    api_url_path = url
    method = "POST"
    string_to_sign = method + api_url_path + json.dumps(body) + nonce
    signature_prefix = "dmar ed25519 "
    encoded = string_to_sign.encode('utf-8')
    signature_bytes = crypto_sign(encoded, bytes.fromhex(sKey))
    signature = signature_bytes[:64].hex()
    headers = {
        "X-Api-Key": pKey,
        "X-Request-Sign": signature_prefix + signature,
        "X-Sign-Date": nonce
    }
    return headers
    #-------------------------------------------------------------------

def get_targets(pKey,sKey):
    
    cursor=None
    params=""
    
    targ_response = []
    
    while True:
        
        if cursor:
            params = "&cursor="+str(response["cursor"])
    
        headers = encryption_get(pKey,sKey,"/marketplace-api/v2/user/targets?gameId=a8db&limit=100")
    
        response = json.loads(requests.get("https://api.dmarket.com/marketplace-api/v2/user/targets?gameId=a8db&limit=100", headers=headers).text)
    
        targ_response.extend(response["items"])

        cursor = response["cursor"]
        
        if not cursor:
            break
        
    return targ_response
    
targets = get_targets(public_key,secret_key)

if __name__ == "__main__":
    for target in targets:
        
        body = {
            "Targets": [
                {
                    "TargetID": target.get('targetId')
                }
            ]
        }
        #delete target
        headers = encryption_post(body,public_key,secret_key,"/marketplace-api/v1/user-targets/delete")
        resp = requests.post("https://api.dmarket.com/marketplace-api/v1/user-targets/delete", json=body, headers=headers) 
        
    print("All targets deleted")
   
