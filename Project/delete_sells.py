
import os,sys
import requests,json,math

from datetime import datetime

from nacl.bindings import crypto_sign  
"""
    Script requests from Dmarket server active sell offers, prepare headers and requests and sends POST requests
    to delete 25% of each item active sells
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

def encryption_delete(pKey,sKey,url,body):   
     
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

cursor = ''
active_offers = {}
params=""
total_count = 0

while True:
    if cursor != "":
            params = "&cursor="+str(cursor)
        
    response = json.loads(requests.get("https://api.dmarket.com/marketplace-api/v2/user/offers?gameId=a8db&limit=100"+params,headers=encryption_get(public_key,secret_key,"/marketplace-api/v2/user/offers?gameId=a8db&limit=100"+params)).text)
    
    cursor = response["cursor"]
    
    
    
    response = response["items"]  

    
    if len(response) == 0:
        break
    
    for item in response:
        if item["attributes"]["title"] not in active_offers.keys():
            active_offers[item["attributes"]["title"]] = [{"itemId":item["attributes"]["id"], "offerId": item["offerId"],"price":{ "amount": str(item["priceCents"]) ,"currency": "USD"}, "date_creation": item["createdAt"]}]
            total_count += 1
        else:
            active_offers[item["attributes"]["title"]].append({"itemId":item["attributes"]["id"], "offerId": item["offerId"],"price":{ "amount": str(item["priceCents"]) ,"currency": "USD"}, "date_creation": item["createdAt"]})
            total_count += 1
    
    if cursor == "":
        break

print("#------------------------------------------------------------------#")
print(f"Total Offers: {total_count}\n")


for key in active_offers.keys():
    
    length = len(active_offers[key])
    
    quarter = math.ceil(length / 4)
    
    active_offers[key] = active_offers[key][-quarter:]


# One representative offer per title (the first of the retained slice) is
# deleted, batched 100 at a time through the v2 batchDelete endpoint.
requests_list = []
for offer,data in active_offers.items():
    requests_list.append({"offerId" : data[0]["offerId"]})

for i in range(0,math.floor(len(requests_list)/100),100):

    body = {"requests" : requests_list[i*100:100*(i+1)]}

    resp = requests.post("https://api.dmarket.com/marketplace-api/v2/offers:batchDelete",json = body,headers=encryption_delete(public_key,secret_key,"/marketplace-api/v2/offers:batchDelete",body)).json()

    print(str(len(resp["offers"])) + " offers deleted ")
    print(str(len(resp["failed"])) + " offers failed to delete")
    print("Failed offers:" + str(resp["failed"]) +"\n")

body = {"requests" : requests_list[math.floor(len(requests_list)/100)*100:math.floor(len(requests_list)/100)*100+(len(requests_list)%100)]}

resp = requests.post("https://api.dmarket.com/marketplace-api/v2/offers:batchDelete",json = body,headers=encryption_delete(public_key,secret_key,"/marketplace-api/v2/offers:batchDelete",body)).json()

print(str(len(resp["offers"])) + " offers deleted ")
print(str(len(resp["failed"])) + " offers failed to delete\n")
print("Failed offers:" + str(resp["failed"])+"\n")

print("Delete Sells script completed on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("#--------------------------------------------------------------------------------------#\n")
