
import os,sys,requests,json,time

from enum import Enum
from pathlib import Path
from datetime import datetime,timedelta
from nacl.bindings import crypto_sign
import pandas as pd
"""
    Sixth Script is one of most important parts
    - Collects the data of the currently holding items, balance of the account
    - Updates the selling history as well as archive where all the selling history is backed up
    
    Input:
        - ReducedFees: SQL table with info of items that have reduced commision fees on the market
        - skins_offers: SQL table two variables needed RSP and RSP spread
    Output:
        - Items_On_Hold: SQL table and EXCEL file that contains all items which the operating account is currently holds
        - Selling_History: SQL table and Excel file with all sold items on that account with dates and prices
        - 09.2026_sales (example): appends the sold items to the existing archive files or creates new one
            (new month - new file) 
"""
_main_directory = Path(__file__).resolve().parent.parent
_trading_results = _main_directory / "trading_results"


# Make the shared SQL storage layer importable regardless of working directory.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import db

# ---------------------------------------------------------------
# Load the DMarket API keys securely (env / .env / JSON fallback)
import credentials
public_key, secret_key = credentials.load_api_keys()

# ---------------------------------------------------------------
#---------------------------------------------------------------

fees_file = db.read_table("reduced_fees")
fees_names = fees_file["Item Name"].tolist()
fees_list = fees_file["Fee"]
# ---------------------------------------------------------------


skins_offers_file = db.read_table("skins_offers")
offers_names = skins_offers_file["Item Name"].tolist()
offers_rsp = skins_offers_file["RSP"].tolist()
offers_spread = skins_offers_file["RSP-HTP Spread"].tolist()

# ----------------------------------------------------------------

existing = db.read_table("items_on_hold")


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
    #-------------------------------------------------------------------
    
    return headers


def get_invetory_items(targets_closed):

    cursor = None 
    params= ""
    
    inventory = dict()
    while True:
        
        if cursor:
            params = "&cursor="+str(response["cursor"])

        response = json.loads(requests.get("https://api.dmarket.com/marketplace-api/v2/user/inventory?gameId=a8db&treeFilters=inMarket=true&limit=100"+params,headers=encryption_get(public_key,secret_key,"/marketplace-api/v2/user/inventory?gameId=a8db&treeFilters=inMarket=true&limit=100"+params)).text)

        
        items = response["items"]
        
        for asset in items:
            
            id = asset["attributes"]["id"]
            
            title = asset["attributes"]["title"]
            
            if id in targets_closed.keys():
                
                if title in fees_names:
                    
                    fees = float(targets_closed[id]["Price"]) * float(fees_list[fees_names.index(title)])
                else:
                    fees = float(targets_closed[id]["Price"]) * 0.1
                    
                fees = round(fees,3)
                    
                    
                inventory[id] = {"Title": title, "Purchase Price": targets_closed[id]["Price"], "Fee": fees, "Purchase Date": targets_closed[id]["PurchaseDate"]}

        cursor = response["cursor"]
        
        if not cursor:
            break
        
    return inventory

def get_closed_targets():
    #Fetching all bought items into smaller requests by 100
    cursor = None
    params=""
    closed_targets = {}
    
    
    while True:

        if cursor:
            params = "&Cursor=" + str(cursor)

        headers = encryption_get(public_key,secret_key,"/marketplace-api/v1/user-targets/closed?OrderDir=desc&TargetClosed.From=1725152400&Limit=100" + params)

        market_response_closed_Targets = json.loads(requests.get("https://api.dmarket.com/marketplace-api/v1/user-targets/closed?OrderDir=desc&TargetClosed.From=1725152400&Limit=100"+params,headers=headers).text)
        
        for target in market_response_closed_Targets["Trades"]:
            
            if target["Status"] != "reverted":
                
                date = int(target["ClosedAt"])
                
                try: 
                    date = datetime.fromtimestamp(date)
                except (ValueError,OSError,OverflowError):
                    date = "Unknown"
                    
                closed_targets[target["AssetID"]] = {"Price": target["Price"]["Amount"], "Title": target["Title"], "PurchaseDate": date}

                
            else:
                pass

        cursor = market_response_closed_Targets.get("Cursor")
        
        if not cursor:
            break
    return closed_targets
       

def get_closed_offers():
    
    cursor = None
    params=""
    closed_market_offers = {}

    

    while True:

        if cursor:
            params = "&Cursor=" + str(cursor)

        headers = encryption_get(public_key,secret_key,"/marketplace-api/v1/user-offers/closed?OrderDir=desc&OfferClosed.From=1725152400&Limit=100" + params)
        
        market_response_sold = json.loads(requests.get("https://api.dmarket.com/marketplace-api/v1/user-offers/closed?OrderDir=desc&OfferClosed.From=1725152400&Limit=100" +  params ,headers=headers).text)

        for item in market_response_sold["Trades"]:
            if item["Status"] != "reverted":

                date = int(item["OfferClosedAt"])
                
                try:
                    date = datetime.fromtimestamp(date)
                except (OverflowError,OSError,ValueError):
                    date = "Unknown"
                
                closed_market_offers[item["AssetID"]] = {"Title": item["Title"], "Price": float(item["Price"]["Amount"]), "Amount": item["Amount"], 'Sold Date': date,"Fees": float(item["Fee"]["Amount"]["Amount"]), "Status": item["Status"]}
        cursor = market_response_sold.get("Cursor")

        if not cursor:
            break

        time.sleep(0.2)
    return closed_market_offers
           
# Balance of trade protected cash 
def get_blocked_cash():
    headers = encryption_get(public_key,secret_key,"/account/v1/balance")
    
    response = json.loads(requests.get("https://api.dmarket.com/account/v1/balance",headers=headers).text) 
    
    blocked_cash = float(response["usdTradeProtected"])/100
    
    return blocked_cash
    
  
def get_active_sells(targets_closed):
    cursor = None
    params=""
    inventory_items = dict()
    
    while True:
    
        if cursor:
            params = "&cursor="+str(cursor)

        headers = encryption_get(public_key,secret_key,"/marketplace-api/v2/user/offers?gameId=a8db&limit=100"+params)

        response =  json.loads(requests.get("https://api.dmarket.com/marketplace-api/v2/user/offers?gameId=a8db&limit=100"+params,headers=headers).text)
        
        for item in response["items"]:
                
            id = item["attributes"]["id"]
            
            if item["attributes"]["title"] in fees_names:
                
                fees = float(item["priceCents"])/100 * float(fees_list[fees_names.index(item["attributes"]["title"])])
            else:
                fees = (float(item["priceCents"])/100) * 0.1
            
                
            fees = round(fees,3)
            
            inventory_items[id] ={"Title": item["attributes"]["title"], "Purchase Price": targets_closed[id]["Price"], "Fee": fees, "Purchase Date": targets_closed[id]["PurchaseDate"]}

        cursor = response["cursor"]

        if not cursor:
            break
        
    return inventory_items
    
def calculate_assets_value(assets=dict()):
    
    total = 0
    
    for key,asset in assets.items():
        total += round(float(asset["Purchase Price"]),2)                    

    return total


def get_offer_from_market(name, limit="1"):

    # Wildcard ("%") search: the order book read used for PTR 10 relies on fuzzy
    # title matching, NOT exact percent-encoding. Returns both the cheapest
    # offer (lower bound) and the deepest offer in the requested window
    # (ptr bound, already converted to dollars).
    search_name = name.replace(" | ", "%").replace("(", "%").replace(" ", "%").replace(")", "%")

    start = int(limit)

    while True:

        market_repsonse = requests.get(
            "https://api.dmarket.com/exchange/v1/market/items?gameId=a8db&title=" + search_name + "&limit=" + str(
                start) + "&orderBy=price&orderDir=asc&treeFilters=not_category_0%5B%5D=not_stattrak_tm,category_1%5B%5D=not_souvenir&currency=USD")
        offers = json.loads(market_repsonse.text)["objects"]

        if (offers[-1]["title"].find("StatTrak") != -1):
            start += 1
            time.sleep(0.2)
        else:

            lower_bound_price = offers[-1].get("price").get("USD")
            time.sleep(0.2)
            break

    while True:

        limit = start + int(limit)

        market_repsonse = requests.get(
            "https://api.dmarket.com/exchange/v1/market/items?gameId=a8db&title=" + search_name + "&limit=" + str(
                limit) + "&orderBy=price&orderDir=asc&treeFilters=not_category_0%5B%5D=not_stattrak_tm,category_1%5B%5D=not_souvenir&currency=USD")
        offers = json.loads(market_repsonse.text)["objects"]

        if (offers[-1]["title"].find("StatTrak") != -1):
            limit = int(limit) + 1
            time.sleep(0.2)
        else:
            price = float(offers[-1].get("price").get("USD")) / 100
            break

    return price




closed_targets = get_closed_targets()

#Combines items from active sells and items that stays in inventory, since they are seperated apart
inventory_items = { **get_invetory_items(closed_targets), **get_active_sells(closed_targets)}   

# Closed offers also tell us how much cash is blocked in trade-protected sales.
closed_offers = get_closed_offers()


# Free cash and blocked cash are all available through direct request on balance
free_cash = round(float(json.loads(requests.get("https://api.dmarket.com/account/v1/balance",headers=encryption_get(public_key,secret_key,"/account/v1/balance")).text)["usd"]) / 100, 2)
print(f'Cash = {round(free_cash)}')

blocked_cash = get_blocked_cash()
print(f"Blocked Cash = {blocked_cash}")

assets_value = calculate_assets_value(inventory_items)
print(f"Assets Value = {round(float(assets_value),2)}")

total_value = round(float(assets_value) + free_cash + blocked_cash,2)

print(total_value)

selling_history = []

items_on_hold = []

for asset_id, target in closed_targets.items():
    if asset_id in closed_offers.keys():
        row ={
            "Asset Id": asset_id,
            "Item Name": target["Title"],
            "Purchased Price": round(float(target["Price"]),2),
            "Purchased Date": target["PurchaseDate"],
            "SP(-C)": round(closed_offers[asset_id]["Price"] - closed_offers[asset_id]["Fees"],2),
            "Sold Date": closed_offers[asset_id]["Sold Date"],
            "Sale Price": round(closed_offers[asset_id]["Price"],2)
        }
        selling_history.append(row)
        
    elif asset_id in inventory_items.keys():
        try:
            rsp = float(offers_rsp[offers_names.index(target["Title"])])
            spread = float(offers_spread[offers_names.index(target["Title"])])
        except(ValueError):
            rsp = None
            spread = None
        row ={
            "Asset Id": asset_id,
            "Item Name": target["Title"],
            "Purchased Price": target["Price"],
            "Purchased Date": target["PurchaseDate"],
            "RSP": rsp,
            "RSP spread" : spread
        }
        items_on_hold.append(row)
    else:
        pass

df_history = pd.DataFrame(selling_history)
df_hold = pd.DataFrame(items_on_hold)

live_ids = set(df_hold["Asset Id"].astype(str)) if not df_hold.empty else set()
existing_ids = (
    set(existing["Asset Id"].astype(str))
    if not existing.empty and "Asset Id" in existing.columns
    else set()
)
to_delete = existing_ids - live_ids
to_add = live_ids - existing_ids


    
if not df_history.empty:
    now = datetime.now()
    # Filter items sold in current month - handle both datetime and pd.Timestamp
    def is_current_month(x):
        if isinstance(x, datetime):
            return x.year == now.year and x.month == now.month
        elif isinstance(x, pd.Timestamp):
            return x.year == now.year and x.month == now.month
        return False
    
    current_month_sold = df_history[df_history['Sold Date'].apply(is_current_month)]
    
    if not current_month_sold.empty:
        try:
            # Pull whatever is already archived for this month/year from the DB.
            existing = db.query(
                'SELECT * FROM sales_archive WHERE "Month"=? AND "Year"=?',
                (now.month, now.year),
            ) if db.table_exists("sales_archive") else pd.DataFrame()

            existing_asset_ids = set()
            if not existing.empty and 'Asset Id' in existing.columns:
                existing_asset_ids = set(existing['Asset Id'].astype(str))

            # Filter out items that already exist by AssetID
            new_rows = current_month_sold[
                ~current_month_sold['Asset Id'].astype(str).isin(existing_asset_ids)
            ].copy()

            archive_file_name = f"sales_{now.month:02d}_{now.year}.xlsx"
                
            if not new_rows.empty:

                new_rows['Month'] = now.month
                new_rows['Year'] = now.year

                # Append the new rows to the single sales_archive table.
                db.append_table(new_rows, "sales_archive")

            # Mirror this month's archive to its own Excel file too.
            if db.excel_enabled():
                month_rows = db.query(
                    'SELECT * FROM sales_archive WHERE "Month"=? AND "Year"=?',
                    (now.month, now.year),
                ).drop(columns=["Month", "Year"], errors="ignore")
                archive_dir = os.path.join(_trading_results, "archive")
                archive_path = os.path.join(archive_dir, f"sales_{now.month:02d}_{now.year}.xlsx")
                db.write_excel_sheet(month_rows, archive_path, "Sheet1")

                print(f"Archived {len(new_rows)} new items for {now.month:02d}/{now.year}")
            else:
                print(f"All items already exist in archive, nothing to add")
        except Exception as e:
            print(f"Error archiving: {e}")
    else:
        print(f"No items sold in current month ({now.month}/{now.year}) to archive")


# Keep prior sales and only insert Asset Ids that are not already stored.
# Do not delete rows missing from this run: the closed-offers API lookback is
# limited, and a full replace would wipe older history (same as items_on_hold
# delete+append, minus the delete).
existing_history = db.read_table("selling_history")
existing_history_ids = (
    set(existing_history["Asset Id"].astype(str))
    if not existing_history.empty and "Asset Id" in existing_history.columns
    else set()
)
live_history_ids = (
    set(df_history["Asset Id"].astype(str))
    if not df_history.empty and "Asset Id" in df_history.columns
    else set()
)
history_to_add = live_history_ids - existing_history_ids
if history_to_add:
    new_history_rows = df_history[df_history["Asset Id"].astype(str).isin(history_to_add)]
    db.append_table(new_history_rows, "selling_history")
if db.excel_enabled():
    db.write_excel_sheet(
        db.read_table("selling_history"),
        "8_Selling_History.xlsx",
        "Sheet1",
    )

# instead of: db.replace_table(df_hold, "items_on_hold")
db.delete_rows("items_on_hold", "Asset Id", to_delete)
if to_add:
    new_hold_rows = df_hold[df_hold["Asset Id"].astype(str).isin(to_add)]
    db.append_table(new_hold_rows, "items_on_hold")
if db.excel_enabled():
    db.write_excel_sheet(
        db.read_table("items_on_hold"),
        "7_Items_on_Hold.xlsx",
        "Sheet1",
    )

# Keep the single values available for fast programmatic access (e.g. script 7
# reads ``assets_value`` from here when sizing targets). ``cash`` is the
# spendable balance (total balance minus the blocked, trade-protected funds).
db.set_meta("cash", free_cash)
db.set_meta("blocked_cash", blocked_cash)
db.set_meta("assets_value", float(assets_value))
db.set_meta("Total Capital", total_value)

# Cash / blocked cash / assets value live in their own ``portfolio`` table

portfolio = pd.DataFrame([{
    "Free cash": free_cash,
    "Blocked Cash": blocked_cash,
    "Assets Value": float(assets_value),
    "Total Capital" : total_value
}])
db.replace_table(portfolio, "portfolio")


print("Transaction history has been updated")
    


















