import os,sys,requests,json,math

from dmarket_client import DMarketClient

import pandas as pd

# Make the shared SQL storage layer importable regardless of working directory.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import db


# ---------------------------------------------------------------

import credentials
public_key, secret_key = credentials.load_api_keys()


# ---------------------------------------------------------------


reduced_fees = dict()


client = DMarketClient(public_key,secret_key)
payload = {
    "gameId" : "a8db",
    "offerType" : "dmarket",
    "limit" : 100000
}
result,err = client.call("GET", "/exchange/v1/customized-fees",payload=payload)


reduced = result["reducedFees"]

for item in reduced:
    reduced_fees[item["title"]] = [item["fraction"],float(item["maxPrice"])/10000]


# -- reduced fees table constructor
all_data = []
for skin_name, data in reduced_fees.items():
    row = {
        'Item Name': skin_name,
        F"Fee": data[0],
        f"Max Price": data[1],

    }
    all_data.append(row)


df_all = pd.DataFrame(all_data)
# --- finish constructing
db.replace_table(df_all, "reduced_fees")
