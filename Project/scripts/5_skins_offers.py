import os,sys,requests,json,time,asyncio, aiohttp

from datetime import datetime

from nacl.bindings import crypto_sign

import pandas as pd


""" Fifth script contains all the items that passed algorithm checks.
    Its job is to collect all the data needed for quantity and bid price calculation
    Input:
        - Reduced Fees: SQL table of items that have reduced market fees on Dmarket marketplace(10% -> 2%)
        - Skins_MWV: SQL Table containing minimum weekly trading volume value for each item
        - skins_history_indicators: SQL Table containing params for calculation of PTR10 and PTR20
    Uses:
        asyncio & aiohttp as previously for parallel requests and execution
    Output:
        - skins_offers SQL table with all parameters for target creation script
        """
# Make the shared SQL storage layer importable regardless of working directory.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
        
import db
import dmarket_urls
import credentials

from dmarket_client import DMarketClient

public_key, secret_key = credentials.load_api_keys()

LO_SPREAD = 3

# ---------------------------------------------------------------

file_mwv = db.read_table("skins_mwv")
mwv_items = file_mwv["Item Name"].tolist()
mwv_itemMWV = file_mwv["Min Week"].tolist()

# ---------------------------------------------------------------
file_indicators = db.read_table("skins_history_indicators")
ptr_10_var = file_indicators["Min Week / 10"].tolist()
ptr_20_var = file_indicators["Min Week / 5"].tolist()
# ---------------------------------------------------------------
fees_file = db.read_table("reduced_fees")
fees_names = fees_file["Item Name"].tolist()

# ---------------------------------------------------------------

ASSETS_BALANCE = db.get_meta("assets_value",type=float)
cash_balance = db.get_meta("cash",type=float)  
blocked_balance = db.get_meta("blocked_cash",type=float)


# ---------------------------------------------------------------
offers_info = {}

semaphore = asyncio.Semaphore(1)

def get_highest_target(name):
    
    
    search_name = dmarket_urls.encode_title(name)
    
    market_response = requests.get("https://api.dmarket.com/marketplace-api/v1/market-depth?gameId=a8db&title="+search_name+"&aggregatedData=Orders")
    offers = json.loads(market_response.text)["orders"]
    for target in offers:
        if target.get("attributes") == []:
            return target



async def get_offer_from_market(session, client, name, ptr_10, ptr_20):
    LO_results = [0,0,0]
    results = {}
    
    payload = {
                    "gameId" : "a8db",
                    "title" : name,
                    "limit" : "1",
                    "orderBy" : "price",
                    "orderDir" : "asc",
                    "treeFilters" : "not_category=stattrak_tm,not_category=souvenir"
                    }
    
    for i in range(3):
        async with semaphore:
            try:
                response, err = await client.acall(session,"GET", "/marketplace-api/v2/offers", payload)

                offers = response.get("items")
                if (offers[-1]["attributes"]["title"].find("StatTrak") != -1):
                    payload["limit"] = str(int(payload["limit"])+1)
                    await asyncio.sleep(0.2)

                else:
                    LO_results[i] = float(offers[-1].get("priceCents"))/100
                    payload["limit"] = str(int(payload["limit"])+1)
                    await asyncio.sleep(0.2)
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError):
                pass
                
    results[name] = LO_results


    for i in range(2):
        if i == 0: 
            payload["limit"] = str(ptr_10)
        else:
            payload["limit"] = str(ptr_20)
        async with semaphore:
            try:
                response,err = await client.acall(session, "GET", "/marketplace-api/v2/offers", payload=payload)
                offers = response.get("items")
                if (offers[-1]["attributes"]["title"].find("StatTrak") != -1):
                        payload["limit"] = str(int(payload["limit"])+1)
                        time.sleep(0.2)
                else:
                    results[name].append(float(offers[-1].get("priceCents"))/100)
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError):
                    pass
    
    return results

BALANCE = blocked_balance + cash_balance
print(f"Balance: {BALANCE} ")


async def api_requests():
    client = DMarketClient(public_key,secret_key)
    async with aiohttp.ClientSession() as session:
        tasks = [get_offer_from_market(session,client,name,ptr_10_var[i],ptr_20_var[i]) for i,name in enumerate(mwv_items)]
        return await asyncio.gather(*tasks)
    
responses = asyncio.run(api_requests())


for response in responses:
    
    for item,values in response.items():
        
    
        HTP_response = get_highest_target(item)

        if (None in values):
            pass
        else:
            RSP = values[2] #RSP value
            if item in fees_names:
                
                spread = round(RSP*0.98,2)
            else:
                spread = round(RSP*0.9,2)

            spread = (spread / (float(HTP_response.get("price"))/100+0.01)) - 1

            ind = mwv_items.index(item)
            
            offers_info[item] = [float(HTP_response.get("price"))/100, HTP_response.get("amount"), float(values[0]), float(values[1]),float(values[2]), float(values[3]), float(values[4]), str(float(HTP_response.get("price"))/100+0.01),RSP ,round(spread,2), mwv_itemMWV[ind]] 
    
all_data =[]

for skin_name, data in offers_info.items():
    row = {
        'Item Name': skin_name,
        F"Highest Target Price": data[0],
        f"Target amount": int(data[1]),
        f"Lowest Offer Price" : data[2],
        f"2nd Lowest Offer": data[3],
        f"3rd Lowest Offer": data[4],
        f"PTR10": data[5],
        f"PTR20": data[6],
        f"MaxTP" : float(data [7]),
        f"RSP": data[8],
        f"RSP-HTP Spread" : data[9],
        f"Min Week" : data[10]
    }
    all_data.append(row)
    
df_all = pd.DataFrame(all_data)

db.replace_table(df_all, "skins_offers")

print("Skins_offers been updated")