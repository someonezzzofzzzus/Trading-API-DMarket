# ---------------------------------------------------------------
import os,sys

import pandas as pd
"""Forth script used as intermidiary step, to cast aside useless info and collect additional data if needed
    Input: 
        - SQL Table (skins_mwv) with last 4 weeks and minimum week columns
    Output:
        - SQL Table (skins_history_indicators) with variables that will be required later on the script
"""
# Make the shared SQL storage layer importable regardless of working directory.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import db

# ---------------------------------------------------------------


file = db.read_table("skins_mwv")
skins_name = file["Item Name"].tolist()

min_week = file["Min Week"].tolist()

indicators = {}

for i in range(len(skins_name)):
    indicators[skins_name[i]] = [min_week[i],round(min_week[i]/10),round(min_week[i]/5)]
  
  
  
    
all_data =[]   
   
for name,data in indicators.items():
    row = {
            "Item Name" : name,
            "Min Week": data[0],
            f"Min Week / 10": data[1],
            f"Min Week / 5": data[2]
    }
    all_data.append(row)

df_all = pd.DataFrame(all_data) 

db.replace_table(df_all, "skins_history_indicators")
