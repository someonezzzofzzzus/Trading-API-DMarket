from multiprocessing import Value
import os,sys,time,requests,json,math
import asyncio,aiohttp
from datetime import datetime,timedelta

from nacl.bindings import crypto_sign  

import pandas as pd
"""The script analyzes the market, collect actual prices for items, creates headers and selling params for items
    and send POST sell request to put all items on market that are in inventory and have been bought by the script 
    Input:
        - Items_On_Hold: SQL Table with purchase date, purchase price and RSP spread variable that are used for 
                         sale creation 
        - ReducedFees: SQL Table of items that have reduced market commision fees for sale (10% -> 2%)
    Output:
        - Prints quantity of items successfully posted for sale and prints number of failed items"""
# Make the shared SQL storage layer importable regardless of working directory.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from dmarket_client import DMarketClient
import db
import dmarket_urls

# ---------------------------------------------------------------

import credentials
public_key, secret_key = credentials.load_api_keys()

RSP_LO = 3
semaphore = asyncio.Semaphore(1)
#---------------------------------------------------------------

fees_file = db.read_table("reduced_fees")

fees_names = fees_file["Item Name"].tolist()
max_prices = fees_file["Max Price"].tolist()
fee_dict = dict()

for i in range(len(fees_names)):
    if max_prices[i] is list:
        fee_dict[fees_names[i]] = tuple(max_prices[i])
    else:
        fee_dict[fees_names[i]] = max_prices[i]

# ---------------------------------------------------------------
items_on_hold = dict()

inventory_file = db.read_table("items_on_hold")
ids = inventory_file["Asset Id"].tolist()
names = inventory_file["Item Name"].tolist()
pps = inventory_file["Purchased Price"].tolist()
rsp_spread = inventory_file["RSP spread"].tolist()
# Purchased date drives the resale markup tiers further below; coerce to
# Timestamps so the datetime comparisons work regardless of how the DB stored it.
date = pd.to_datetime(inventory_file["Purchased Date"], errors="coerce")
for i in range(len(ids)):
    items_on_hold[ids[i]] = [names[i],pps[i],date[i], rsp_spread[i]]
#--------------------------------------------------------------------
total_info_of_sales = {}

# for passed offers history
all_item_history = {}

rootApiUrl = "https://api.dmarket.com"

#Function to check if the current date is after the last Sunday date
async def get_offer_from_market(client, name, limits=3):
    # Prevent infinite recursion by limiting attempts
    if limits > 15:
        return f"Item {name} has not been found"

    
    payload = {
        "gameId" : "a8db",
        "title" : name,
        "limit" : limits,
        "orderBy" : "price",
        "orderDir" : "asc",
        "treeFilters" : "not_category=stattrak_tm,not_category=souvenir"
        }
         
    response, err = await client.acall("GET", "/marketplace-api/v2/offers", payload=payload)

    
    # if response.status != 200:
    #     print(response.status)
    
    if not err:
        offers = response.get("items")
        if len(offers) <= 0:
            return f"Item {name} has not been found"
        last_offer = offers[-1]
        title = last_offer.get("attributes").get("title")
        if title.find("StatTrak") != -1 or title.find("Souvenir") != -1:
            new_limits = limits + 2
            if limits >= 10:
                return f"Item {name.replace('%', ' ')} only available as StatTrak/Souvenir"
            return get_offer_from_market(client, name, new_limits)
        
        return last_offer
    elif response.status == 429:
        time.sleep(0.05)
        get_offer_from_market(client, name, limits)
    else:
        return None

def week_pass(date):
    
    
    date1 = datetime.strptime(date,"%d.%m.%Y" )
    
    if datetime.now() > date1 + timedelta(weeks=1):
        return True
    else:
        return False
    
    
#Function to get the number of items sold in the last 4 weeks
def get_weeks_count(item_history=None):
    
    if item_history is None:
        item_history = list()
    items_per_week_count = [0,0,0,0]
    
    for sale in item_history:
        
        sale_date = datetime.fromtimestamp(int(sale.get("date")))
        
        if sale_date  < last_sunday:
            if sale_date > (last_sunday - timedelta(weeks=4)):
                if sale_date > (last_sunday - timedelta(weeks=1)):
                    items_per_week_count[0] += 1
                elif sale_date > (last_sunday - timedelta(weeks=2)):
                    items_per_week_count[1] += 1
                elif sale_date > (last_sunday - timedelta(weeks=3)):
                    items_per_week_count[2] += 1
                elif sale_date > (last_sunday - timedelta(weeks=4)):
                    items_per_week_count[3] += 1
            else:
                pass
        else:
            pass
    
    return items_per_week_count


#Function to sort the sales  information
def sorting_sales_info(item_history):
    price_list=[]
    date_list=[]
    offer_type=[]
    
    for item_info in item_history:
        price_list.append(float(item_info.get("price")))
        date_list.append(datetime.fromtimestamp(int(item_info.get("date"))))
        offer_type.append(item_info.get("txOperationType"))
    
    return [price_list,date_list,offer_type]

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
    #-------------------------------------------------------------------
    return headers

def get_latest_sunday(dt):
    
    days_to_subtract = (dt.weekday() + 1) % 7  # Sunday is 6, Monday is 0
    last_sunday = dt - timedelta(days=days_to_subtract)
    
    # Set the time to 23:59:59
    last_sunday_at_235959 = last_sunday.replace(hour=23, minute=59, second=59, microsecond=0)
    
    return last_sunday_at_235959


last_sunday = get_latest_sunday(datetime.now())

def get_sales_history(name,offset):
    #function requesting the trading history with limits of 500
            
    # ---------------------------------------------------------------
    nonce = str(round(datetime.now().timestamp()))
    api_url_path = f"/trade-aggregator/v1/last-sales?gameId=a8db&title="+name+f"&limit=500&offset="+str(offset)

    #Encryption process for reqests
    method = "GET"
    string_to_sign = method + api_url_path + nonce
    signature_prefix = "dmar ed25519 "
    encoded = string_to_sign.encode('utf-8')
    signature_bytes = crypto_sign(encoded, bytes.fromhex(secret_key))
    signature = signature_bytes[:64].hex()
    headers = {
        "X-Api-Key": public_key,
        "X-Request-Sign": signature_prefix + signature,
        "X-Sign-Date": nonce
    }
    #-------------------------------------------------------------------
    
    
    
    market_response = json.loads(requests.get(rootApiUrl + api_url_path, headers=headers).text)
    return market_response.get('sales')

def encryption_post(pKey,sKey,body):
    
    # ---------------------------------------------------------------
    nonce = str(round(datetime.now().timestamp()))  
    api_url_path = "/marketplace-api/v2/offers:batchCreate"

    #Encryption process for reqests
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
    #-------------------------------------------------------------------
    return headers



cursor = None
params = ""
inventory_items = {}
while True:
    if cursor:
        params = "&cursor="+str(cursor)

    inv_path = "/marketplace-api/v2/user/inventory?gameId=a8db&treeFilters=inMarket=true&limit=100"+params
    inventory = json.loads(requests.get("https://api.dmarket.com"+inv_path,headers=encryption_get(public_key,secret_key,inv_path)).text)
    
    
    
    for item in inventory["items"]:

        asset_id = item["attributes"]["id"]

        if asset_id in ids:    
            inventory_items[asset_id] = [items_on_hold[asset_id],item["attributes"]["title"]]

    cursor = inventory["cursor"]

    if not cursor:
        break
    
    
cursor = None
params = ""
while True:
    
    if cursor:
        params = "&cursor="+str(cursor)

    offers_path = "/marketplace-api/v2/user/offers?gameId=a8db&limit=100"+params
    user_offers = json.loads(requests.get("https://api.dmarket.com"+offers_path,headers=encryption_get(public_key,secret_key,offers_path)).text)
    
    for item in user_offers["items"]:

        asset_id = item["attributes"]["id"]

        if asset_id in items_on_hold.keys():

            items_on_hold.pop(asset_id,None)    

    cursor = user_offers["cursor"]

    if not cursor:
        break

offers = []
print("#--------------------------------------------------------------------------------------#\n")
print("Data of Inventory was collected at "+ datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
for key,data in items_on_hold.items():

    
    
    item = data[1]

    offset = 0

    if key in items_on_hold.keys():

        client = DMarketClient(public_key,secret_key)
        
        name = items_on_hold[key][0]
        pp = float(items_on_hold[key][1])
        rsp = float(get_offer_from_market(client, name, 3)["priceCents"])/100
        spread = float(items_on_hold[key][3])
        date = items_on_hold[key][2]
        
        if rsp is None:
            raise ValueError("RSP value has not been found")
        
        if spread < 0:
            spread = 0
        
        sel_price = rsp
                
        sel_price*=100
        sel_price = int(sel_price)

        
        offers.append({"assetId":key,"priceCents": sel_price})

print("Selling Offers starting be created on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") )
print(f"Number of selling offers for creation {len(offers)} \n")

if len(offers) > 0:
    for g in range(0,math.floor(len(offers)/100)):
        body = {"requests":offers[g*100:100*(g+1)]}

        response = requests.post("https://api.dmarket.com/marketplace-api/v2/offers:batchCreate",headers=encryption_post(public_key,secret_key,body),json=body)

        if response.status_code == 200:
            print("Offers been created successfully: " + str(len(response.json()["offers"])) )
            print("Offers failed to create: " + str(len(response.json()["failed"])))
            print("Failed creation: " + str(response.json()["failed"]) + "\n")
        else:
            print("Script failed to send creation request with and error: " + str(response.status_code))
            print(response.json())

    body  = {"requests":offers[math.floor(len(offers)/100) *100: math.floor(len(offers)/100) *100 + len(offers)%100 ]}

    response = requests.post("https://api.dmarket.com/marketplace-api/v2/offers:batchCreate",headers=encryption_post(public_key,secret_key,body),json=body)

    if response.status_code == 200:
        print("Offers been created successfully: " + str(len(response.json()["offers"])))
        print("Offers failed to create: " + str(len(response.json()["failed"])))
        print("Failed creation: " + str(response.json()["failed"])+"\n")
    else:
        print("Script failed to send creation request with and error: " + str(response.status_code))
        print(response.json())
print("Sell Script finished on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
print("#--------------------------------------------------------------------------------------#\n")
   


    

    


