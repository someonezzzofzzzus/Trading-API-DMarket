import asyncio
import aiohttp
import json
import os
import sys
import time

from datetime import datetime, timedelta
from yarl import URL


import pandas as pd

""" 
    Second script that analyze how many trades were made for the last month
    and find liquid items that are high-volume traded
    Input:
        - Table of items that passed the price range condition(1_Skins.py)
    Uses:
        - asyncio library is used for parallel execution of all requests 
        - aiohttp as a sub-library of asyncio is used for creating one session instead of sending 
          numbers of requests to the server
        - Imports dmarket_client.py DMarketClient class to create headers using Api Keys and sending the 
         requests
    Output:
        - SQL Table containing 4 weeks (per week) volume of trades for each item
        - Excel file 2_skins_weekly_volume.xlsx for manual analyze and finding bugs
"""

# Make the shared SQL storage layer importable regardless of working directory.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import db
import credentials
from Encryption import Encryption
from dmarket_client import DMarketClient

#-----------------------------------------------------------
# Creating variables

# Flag to check if the script is waiting for update
waiting_for_update = False

public_key, secret_key = credentials.load_api_keys()

rootApiUrl = "https://api.dmarket.com"
semaphore = asyncio.Semaphore(1)

#-----------------------------------------------------------
# Flag to check if the skins list is updated
file = db.read_table("skins_ref_price")
skins_names = file["Item Name"].tolist()


#-----------------------------------------------------------
# Check if the weekly history table exists and has the expected schema.
_WEEKLY_VOLUME_COLS = ("Week 01", "Week 02", "Week 03", "Week 04")
history = None

checkDT = db.get_meta("last_sunday_change")
checkDT = datetime.strptime(checkDT, "%Y-%m-%d %H:%M:%S")

if db.table_exists("skins_weekly_volumes"):
    _history = db.read_table("skins_weekly_volumes")
    _has_week_cols = all(col in _history.columns for col in _WEEKLY_VOLUME_COLS)
    _has_items = (
        "Item Name" in _history.columns
        and _history["Item Name"].notna().any()
        and (_history["Item Name"].astype(str).str.strip() != "").any()
    )
    if _has_week_cols and _has_items:
        history = _history


# for passed offers history
all_item_history = {}

# Seconds between API calls to avoid hitting DMarket rate limits.
API_DELAY_SEC = 0.3
# Hard cap so a busy skin (or a stuck offset) cannot grow RAM without bound.
# 20 pages * 500 sales = 10,000 trades, which is enough to cover 4 weeks.
MAX_PAGES = 20
PROGRESS_EVERY = 25

client = DMarketClient(public_key,secret_key)


async def get_sales_history(session, name, offset=None):
    api_url_path = ("/trade-aggregator/v1/last-sales")
    payload = {
        "gameId" : "a8db",
        "title" : name,
        "limit" : 500,
        "offset": offset
    }
    try:
        response,err = await client.acall(session, "GET", api_url_path,payload)
        if response is not None:
            sales = response.get("sales")
            return sales if sales is not None else []
        else:
            raise RuntimeError(err)
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError):
        pass

    return []


# Function to get the latest Sunday date
def get_latest_sunday(dt):
    days_to_subtract = (dt.weekday() + 1) % 7  # Sunday is 6, Monday is 0
    last_sunday = dt - timedelta(days=days_to_subtract)

    # Set the time to 23:59:59
    last_sunday_at_235959 = last_sunday.replace(
        hour=23, minute=59, second=59, microsecond=0
    )

    return last_sunday_at_235959


last_sunday = get_latest_sunday(datetime.now())


four_weeks_ago = last_sunday - timedelta(weeks=4)
six_months_ago = last_sunday - timedelta(weeks=25)


def _sale_datetime(sale):
    if not sale:
        return None
    date_raw = sale.get("date")
    if date_raw is None:
        return None
    try:
        return datetime.fromtimestamp(int(date_raw))
    except (TypeError, ValueError):
        return None


def _add_weeks_count(counts, batch):
    """Tally a page of sales into the 4 week buckets, then the page can be discarded."""
    for sale in batch:
        sale_date = _sale_datetime(sale)
        if sale_date is None:
            continue
        if sale_date < last_sunday:
            if sale_date > (last_sunday - timedelta(weeks=1)):
                counts[0] += 1
            elif sale_date > (last_sunday - timedelta(weeks=2)):
                counts[1] += 1
            elif sale_date > (last_sunday - timedelta(weeks=3)):
                counts[2] += 1
            elif sale_date > (last_sunday - timedelta(weeks=4)):
                counts[3] += 1


async def process_skin(session, item, check_established=False):
    """Fetch one skin's last-sales pages, count weekly volume, drop the page.

    Only the 4 integers are kept. Pagination stops at 4 weeks, MAX_PAGES, or
    when the API stops returning older sales.
    """
    counts = [0, 0, 0, 0]
    offset = 0
    pages = 0
    oldest = None
    prev_oldest = None

    while pages < MAX_PAGES:
        batch = await get_sales_history(session, item, offset)
        await asyncio.sleep(API_DELAY_SEC)
        pages += 1

        if not batch:
            break

        _add_weeks_count(counts, batch)
        oldest = _sale_datetime(batch[-1]) or oldest

        # Offset is not advancing (API repeating the same page) — stop.
        if prev_oldest is not None and oldest is not None and oldest >= prev_oldest:
            break
        prev_oldest = oldest

        if oldest is not None and oldest < four_weeks_ago:
            break
        if len(batch) < 500:
            break
        offset += 500

    established = True
    if check_established:
        established = False
        if oldest is not None and oldest < six_months_ago:
            established = True
        elif pages >= MAX_PAGES:
            # Still inside 4 weeks after 10k sales: this is a liquid skin.
            established = True
        else:
            while pages < MAX_PAGES:
                offset += 500
                batch = await get_sales_history(session, encoded_name, offset)
                await asyncio.sleep(API_DELAY_SEC)
                pages += 1
                if not batch:
                    break
                oldest = _sale_datetime(batch[-1]) or oldest
                if oldest is not None and oldest < six_months_ago:
                    established = True
                    break
                if prev_oldest is not None and oldest is not None and oldest >= prev_oldest:
                    established = True
                    break
                prev_oldest = oldest
                if len(batch) < 500:
                    break
            else:
                established = True

    return counts, established


async def fetch_skins(skins, check_established=False):
    """Process skins one at a time so RAM stays flat (one page, then discard)."""
    async with aiohttp.ClientSession() as session:
        total = len(skins)
        fetched = 0
        for i, item in enumerate(skins, 1):
            counts, established = await process_skin(
                session, item, check_established=check_established
            )
            fetched += 1
            if (not check_established) or established:
                all_item_history[item] = counts
            if i % PROGRESS_EVERY == 0 or i == total:
                print(
                    f"  {i}/{total} skins "
                    f"({len(all_item_history)} with weekly volume)",
                    flush=True,
                )
        return fetched


# Decider to create new file or update existing one
if history is None:
    start = time.time()
    print(f"Fetching sales history for {len(skins_names)} skins...", flush=True)
    fetched = asyncio.run(fetch_skins(skins_names, check_established=True))
    print(f"Fetch finished in {time.time() - start:.1f}s", flush=True)
    print(
        f"Weekly volumes: {len(all_item_history)} established of "
        f"{fetched} skins fetched",
        flush=True,
    )

else:
    if checkDT is None or datetime.now() > checkDT + timedelta(weeks=0):
        start = time.time()
        print(
            f"Updating weekly volumes for {len(skins_names)} skins...",
            flush=True,
        )
        asyncio.run(fetch_skins(skins_names, check_established=False))
        print(f"Fetch finished in {time.time() - start:.1f}s", flush=True)
    else:
        print(
            f"Skipping script because it was last updated on {checkDT} \n "
            f"Next update will be available on {checkDT + timedelta(weeks=1)}"
        )
        waiting_for_update = True

# If the script is not waiting for update, update the database
if not waiting_for_update:
    if not all_item_history:
        print(
            "No weekly volume data to save (no skins met the 6-month history "
            "threshold). Skipping database update."
        )
        waiting_for_update = True

if not waiting_for_update:
    if db.excel_enabled():
        _weekly_xlsx = os.path.join(db.excel_dir(), "2_skins_weekly_history.xlsx")
        if os.path.exists(_weekly_xlsx):
            os.remove(_weekly_xlsx)

    all_data = []
    for skin_name, data in all_item_history.items():
        row = {
            "Item Name": skin_name,
            "Week 01": data[0],
            "Week 02": data[1],
            "Week 03": data[2],
            "Week 04": data[3],
        }
        all_data.append(row)

    mark = {"Last Sunday Change": last_sunday}
    all_data.append(mark)

    df_all = pd.DataFrame(all_data)
    db.replace_table(df_all, "skins_weekly_volumes")
    db.set_meta("last_sunday_change", last_sunday)

    print("WEEKLY VOLUMES HAS BEEN UPDATED", flush=True)
