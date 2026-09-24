# GAFNA

Automated trading tools for Counter-Strike 2 skins on the [DMarket](https://dmarket.com) marketplace.

GAFNA pulls market data through the DMarket API, filters a fixed skin list by price and weekly volume, sizes buy targets from account balance and inventory, and can list purchased items for sale. Results live in a local SQLite database, with Excel workbooks kept in sync for review.

Running the full pipeline places and cancels real orders on the account whose API keys you provide. Review the filters and caps before you point it at a funded account.

## How it works

`Project/run_scripts.py` runs the steps below in order. Each step reads the tables written by the previous one.

| Step | Script | What it does |
| --- | --- | --- |
| 1 | `Fees_Script.py` | Loads items that currently have a reduced DMarket fee. |
| 2 | `delete_targets.py` | Cancels the account’s active buy targets so the next run can replace them. |
| 3 | `scripts/1_Skins.py` | Prices every name in `scripts/Skins_names.py` and keeps items inside the configured price band. |
| 4 | `scripts/2_skins_weekly_history.py` | Collects the last four weeks of sales for those items. This step paginates last-sales and can take up to an hour. |
| 5 | `scripts/3_Skins_mwv.py` | Drops items whose minimum weekly volume is below the threshold (30). |
| 6 | `scripts/4_skins_history_indicators.py` | Builds the volume-derived figures used later for offer depth. |
| 7 | `scripts/5_skins_offers.py` | Reads the offer book and stores the inputs used to price buy targets. |
| 8 | `scripts/6_history_records.py` | Refreshes balance, items on hold, and selling history, and appends the month’s sales archive. |
| 9 | `scripts/7_target_creation.py` | Places new buy targets, capped by weekly volume and account capital. |

Two scripts sit outside that runner and are meant to be scheduled on their own:

- `sell_script.py` lists inventory items that the pipeline bought.
- `delete_sells.py` removes part of the account’s active sell offers.

`gloves_knives_data_collection.py` is a separate research job. It reads glove and knife workbooks next to the script and writes a timestamped workbook of minimum weekly volume and offer prices. It does not place orders.

The shell files in `Project/` (`target_creation_csGem.sh`, `sell_script_csGem.sh`, `delete_sells_csGem.sh`, `register_logs.sh`) are cron wrappers from a Linux host. Paths inside them point at that machine; change them before you reuse the files.

## Requirements

- Python 3.10 or newer
- A DMarket account with API keys (Ed25519 public key and secret)
- Network access to `https://api.dmarket.com`

## Setup

From the repository root:

```bash
cd Project
python -m venv .venv
```

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Create `Project/.env` (this file is gitignored):

```
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key
```

`credentials.py` checks, in order: those environment variables, a `.env` file, then `Project/JSON/config.json` with `public_key` and `secret_key`. Do not commit either file.

## Run

Full pipeline, from `Project/`:

```bash
python run_scripts.py
```

The runner stops with a non-zero exit code if any step fails. Output is printed to the console.

List bought items for sale, after fees and inventory have been refreshed:

```bash
python Fees_Script.py
python scripts/6_history_records.py
python sell_script.py
```

Storage tests do not call DMarket:

```bash
python tests/test_db.py
```

## Data

The database file is `Project/trading_results/trading.db`. Excel copies of the main tables are written beside it unless `TRADING_WRITE_EXCEL` is set to `0`.

| Table | Excel mirror | Contents |
| --- | --- | --- |
| `reduced_fees` | `ReducedFees.xlsx` | Items on a reduced marketplace fee |
| `skins_type_wear`, `skins_ref_price` | `1_Skins.xlsx` | Names that passed the price filter, and reference prices |
| `skins_weekly_volumes`, `skins_sales_history` | `2_skins_weekly_history.xlsx` | Four-week volumes and sale rows |
| `skins_mwv`, `skins_mwv_removed_added` | `3_skins_mwv.xlsx` | Names above the volume threshold, and those dropped |
| `skins_history_indicators` | `4_skins_history_indicators.xlsx` | Volume figures used for offer depth |
| `skins_offers` | `5_skins_Offers.xlsx` | Prices and spreads used to build targets |
| `items_on_hold`, `portfolio` | `7_Items_on_Hold.xlsx` | Inventory the account currently holds |
| `selling_history` | `8_Selling_History.xlsx` | Completed sales |

Monthly sale archives are written under `Project/trading_results/archive/`.

The database, workbooks, and `Project/logs/` are local trading records. They are not required to clone the code, and a public copy of this repository should not include them.

## Configuration

| Variable | Default | Effect |
| --- | --- | --- |
| `DMARKET_PUBLIC_KEY`, `DMARKET_SECRET_KEY` | unset | DMarket API credentials |
| `TRADING_DB_PATH` | `Project/trading_results/trading.db` | SQLite file location |
| `TRADING_EXCEL_DIR` | `Project/trading_results` | Folder for Excel mirrors |
| `TRADING_WRITE_EXCEL` | `1` | Set to `0` to skip Excel writes |

The skin universe is the list in `Project/scripts/Skins_names.py`. Price band, minimum weekly volume (`MWV_THRESHOLD` in `3_Skins_mwv.py`), and target allocation caps live in the scripts that use them.

## Project layout

```
Project/
  credentials.py          API key loading
  dmarket_client.py       Signed HTTP client (sync and async)
  dmarket_urls.py         Item-title encoding
  db.py                   SQLite access and Excel mirrors
  run_scripts.py          Ordered pipeline runner
  Fees_Script.py          Reduced-fee catalog
  sell_script.py          Create sell offers for bought items
  delete_targets.py       Cancel active buy targets
  delete_sells.py         Cancel part of the active sell offers
  scripts/                Pipeline steps 1–7 and the skin name list
  tests/test_db.py        Storage-layer checks
  trading_results/        Database, workbooks, and sales archive
```

## Before you publish

Keep secrets and account data out of the public repository:

- `.env` and `JSON/config.json` (already listed in `.gitignore`)
- API keys, mail credentials, and partner tokens
- `trading.db`, Excel workbooks, and log files

`email_logs.py` can mail the previous day’s log folder. It needs the `sendgrid` package, which is not in `requirements.txt`, and it should read its API key from the environment rather than from source.

## Disclaimer

This is personal trading automation, not financial advice. Skin prices move, API responses fail, and a bug can buy or list the wrong size. You are responsible for the orders the scripts send.
