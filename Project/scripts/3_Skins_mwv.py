import os,sys,json,requests

from datetime import datetime

from nacl.bindings import crypto_sign

import pandas as pd
"""
    Third script that sorts out items that do not pass minimum weekly volume threshold (MWV_THRESHOLD)
    Input:
        - SQL table of skins_weekly_volumes (from previous script)
    Output:
        - SQL table (skins_mwv) that contains all passed items with additional Minimum Weekly value column
        - SQL table (removed_added) that contains items that have not passed the threshold 
    """
# Make the shared SQL storage layer importable regardless of working directory.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import db
import credentials

public_key, secret_key = credentials.load_api_keys()

# ---------------------------------------------------------------
# Creating variables

MWV_THRESHOLD = 30

rootApiUrl = "https://api.dmarket.com"

sheets_name = ["skins_mwv","removed_added"]

# ---------------------------------------------------------------

ASSETS_BALANCE = db.get_meta("assets_value",type=float)
cash_balance = db.get_meta("cash",type=float)  
blocked_balance = db.get_meta("blocked_cash",type=float)
# ---------------------------------------------------------------

# Minimum weekly volume required scales with capital: the more cash on hand, the
# lower the per-week sales bar an item must clear (you can afford slower movers).

BALANCE = blocked_balance + cash_balance

print(f"Balance: {BALANCE} | Min weekly volume threshold: {MWV_THRESHOLD}")

file = db.read_table("skins_weekly_volumes")

_WEEKLY_COLS = ("Item Name", "Week 01", "Week 02", "Week 03", "Week 04")
if not all(col in file.columns for col in _WEEKLY_COLS):
    print(
        "skins_weekly_volumes is missing weekly volume data "
        f"(expected columns: {', '.join(_WEEKLY_COLS)}). "
        "Run 2_skins_weekly_history.py successfully before this script."
    )
    sys.exit(1)

# Drop the trailing marker row (it carries only "Last Sunday Change" and has an
# empty/NaN Item Name) and any other blank-named rows so they don't pollute the
# per-week lists or get processed as a skin.
valid = file["Item Name"].notna() & (file["Item Name"].astype(str).str.strip() != "")
if not valid.any():
    print(
        "skins_weekly_volumes has no skin rows. "
        "Run 2_skins_weekly_history.py successfully before this script."
    )
    sys.exit(1)
file = file.loc[valid].reset_index(drop=True)

skins_names = file["Item Name"].tolist()

week1 = file.iloc[:,1].to_list()
week2 = file.iloc[:,2].to_list()
week3 = file.iloc[:,3].to_list()
week4 = file.iloc[:,4].to_list()


weeks_volumes = {}
removed_items = {}

#Keep the item only if every one of the last 4 weeks met the threshold
def check(item_history):
    for week in item_history:
        if week >= MWV_THRESHOLD:
            pass
        else:
            removed = weeks_volumes.popitem()
            removed_items[removed[0]]= removed[1]
            return False
    
    return True
        
    
for item in skins_names:
    
    item_week_list = [week1.pop(0),week2.pop(0),week3.pop(0),week4.pop(0)]
    
    copy_list = item_week_list.copy()
    copy_list.sort()
    
    item_week_list.append(copy_list[0])
    
    weeks_volumes[item] = item_week_list
    
    if check(weeks_volumes[item]):
        pass

#Items that passed the threshold
#-----------------------------------------------------------   

all_data =[]   
   
for name,data in weeks_volumes.items():
    row = {
            "Item Name" : name,
            "Week 01": data[0],
            "Week 02": data[1],
            "Week 03": data[2],
            "Week 04": data[3],
            "Min Week": data [4]
    }
    all_data.append(row)

df_all = pd.DataFrame(all_data)     

#Items that been removed due to insufficient trading volume
#-----------------------------------------
all_data_2 =[]   
   
for name,data in removed_items.items():
    row = {
            "Item Name" : name,
            "Week 01": data[0],
            "Week 02": data[1],
            "Week 03": data[2],
            "Week 04": data[3]
    }
    all_data_2.append(row)

df_all_2 = pd.DataFrame(all_data_2) 

db.replace_table(df_all, "skins_mwv")
db.replace_table(df_all_2, "skins_mwv_removed_added")
