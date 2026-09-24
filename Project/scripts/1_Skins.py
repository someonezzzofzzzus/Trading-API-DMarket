import asyncio
from math import floor
import aiohttp
import json
import os
import sys
import time
import pandas as pd
from urllib.parse import quote
import Skins_names as sn
from datetime import datetime
from datetime import timedelta

""" 
    First script takes all names from Skins_names.py file and sorts out items that 
    do not pass price criteria range(currently 0.5$ - 3% of *Total Capital)
    - Uses database meta key from trading.db SQL database to gather Total Capital value
    - asyncio library is used for parallel execution of all requests 
    - aiohttp as a sub-library of asyncio is used for creating one session instead of sending 
      numbers of requests to the server
    - Imports dmarket_client.py DMarketClient class to create headers using Api Keys and sending the 
      requests 
    Output: 
        - SQL Table of all the items with their prices that passed
        - Excel file formed out of SQL Table for manual data analysis and archieving if neccessary
"""
# Make the shared SQL storage layer (db.py, located in the Project folder)
# importable regardless of the working directory the script runs from.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import db
import dmarket_urls
import credentials
from dmarket_client import DMarketClient
from dmarket_urls import encode_title


public_key, secret_key = credentials.load_api_keys()

# Check if the skins table exists
if db.table_exists("ref_price"):
    file = db.read_table("ref_price")
    if file.empty:
        file_list = []
    else:
        file_list = file["Item Name"].tolist()
else:
    file_list = []

rootApiUrl = "https://api.dmarket.com"

# Lists of type&wear sheet
sheet1_name = []
sheet1_price = []

# Lists of ref_price sheet
sheet2_name = []
sheet2_price = []

semaphore = asyncio.Semaphore(1)

checkDT = db.get_meta("last_sunday_change")
checkDT = datetime.strptime(checkDT, "%Y-%m-%d %H:%M:%S")

TC = float(db.get_meta("Total Capital"))
TC = floor(TC*0.03)*100

async def get_offer_from_market(session, client, name, limits=3):
    # Prevent infinite recursion by limiting attempts
    if limits > 15:
        return f"Item {name} has not been found"

    
    payload = {
        "gameId" : "a8db",
        "title" : name,
        "limit" : limits,
        "orderBy" : "price",
        "orderDir" : "asc",
        "treeFilters" : "not_category=stattrak_tm,not_category=souvenir",
        "priceTo" : TC
        }

    
    for _ in range(3):
        async with semaphore:   
            url,headers, _ = client.prepare("GET", "/marketplace-api/v2/offers", payload=payload)
            try:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    # Uncomment for troubleshooting
                    # if response.status != 200:
                    #     print(response.status)
                    
                    if response.status == 200:
                        data = await response.json()
                        offers = data.get("items")
                        if len(offers) <= 0:
                            return f"Item {name} has not been found"

                        last_offer = offers[-1]
                        title = last_offer.get("attributes").get("title")
                        #Additional Check for any StatTrak or Souvenir items
                        if title.find("StatTrak") != -1 or title.find("Souvenir") != -1:
                            new_limits = limits + 2
                            if limits >= 10:
                                return f"Item {name.replace('%', ' ')} only available as StatTrak/Souvenir"
                            return await get_offer_from_market(session, client, name, new_limits)
                        
                        return last_offer
                    #HTTP Code for sending to many requests at the same time
                    elif response.status == 429:
                        retry_after = response.headers.get("Retry-After")
                        wait_time = int(retry_after) if retry_after else 2
                        await asyncio.sleep(wait_time)
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError):
                pass

    return f"Network error for {name.replace('%', ' ')}"


async def api_requests():
    client = DMarketClient(public_key,secret_key)
    async with aiohttp.ClientSession() as session:
        tasks = [get_offer_from_market(session,client,name) for name in sn.skins_name]
        return await asyncio.gather(*tasks)
        


start = time.time()

#Main loop
if checkDT < datetime.now() - timedelta(weeks=0):
    
    responses = asyncio.run(api_requests())
    
    for response in responses:

        if type(response) == str:
            pass
        elif response is None:
            pass
        else:
            price = response.get("priceCents")

            #Formating the results(from 45->$0.45 or 123->$1.23)
            if len(price) < 3:
                refer_price = float("0." + price)
                sheet1_name.append(response.get("attributes").get("title"))
                sheet1_price.append(refer_price)
            else:
                refer_price = float(price[:-2] + "." + price[-2:])
                sheet1_name.append(response.get("attributes").get("title"))
                sheet1_price.append(refer_price)
    
    results = {
        "ref_price": [sheet1_name, sheet1_price],
    }
    
    
    table_map = { "ref_price": "skins_ref_price"}

    # Creation of resulting DataFrame
    for sheet_name, data in results.items():
        df = pd.DataFrame(
            {
                "Item Name": data[0],
                "RP": data[1]
            }
        )
    
        db.replace_table(df, table_map[sheet_name])
else: 
    print(
            f"Skipping script because it was last updated on {checkDT} \n "
            f"Next update will be available on {checkDT + timedelta(weeks=1)}"
        )
print(time.time() - start)



