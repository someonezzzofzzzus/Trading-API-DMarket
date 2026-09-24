"""Central SQL storage layer for the DMarket trading project.

Used for manipulation of the database, following rule CRUD
- Creates -> func: set_meta ; write_excel_table; create_table
- Read -> func: read_table; get_meta
- Update -> func: replace_table;append_table;set_meta
- Delete -> func: delete_rows

Switching to another database (PostgreSQL, MySQL, ...) later only requires
changing :func:`get_connection` (e.g. to return a SQLAlchemy engine); the rest
of the code talks to this module, not to SQLite directly.
"""

import os
import sqlite3

import pandas as pd

# ---------------------------------------------------------------------------
# Location of the database file.
#
# Resolved relative to *this* file so the scripts work no matter which working
# directory they are launched from (``Project/`` or ``Project/scripts/``).
# Can be overridden with the ``TRADING_DB_PATH`` environment variable, which is
# handy for tests.
# ---------------------------------------------------------------------------
_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB_PATH = os.path.join(_PROJECT_DIR, "trading_results", "trading.db")

DB_PATH = os.environ.get("TRADING_DB_PATH", _DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# Optional Excel mirroring.
#
# To keep the legacy ``.xlsx`` files in sync with the database, ``replace_table``
# also writes the matching workbook/sheet for tables listed in EXCEL_REGISTRY.
# This can be turned off by setting ``TRADING_WRITE_EXCEL=0`` (e.g. for tests or
# headless servers). The Excel folder defaults to ``trading_results`` next to
# this file and can be overridden with ``TRADING_EXCEL_DIR``.
# ---------------------------------------------------------------------------
_DEFAULT_EXCEL_DIR = os.path.join(_PROJECT_DIR, "trading_results")

# table name -> (workbook file name, sheet name)
EXCEL_REGISTRY = {
    "skins_type_wear": ("1_Skins.xlsx", "type_&_wear"),
    "skins_ref_price": ("1_Skins.xlsx", "ref_price"),
    "skins_weekly_volumes": ("2_skins_weekly_history.xlsx", "skins_weekly_volumes"),
    "skins_sales_history": ("2_skins_weekly_history.xlsx", "skins_sales_history"),
    "skins_mwv": ("3_skins_mwv.xlsx", "skins_mwv"),
    "skins_mwv_removed_added": ("3_skins_mwv.xlsx", "removed_added"),
    "skins_history_indicators": ("4_skins_history_indicators.xlsx", "indicators"),
    "skins_offers": ("5_skins_Offers.xlsx", "offers"),
    "reduced_fees": ("ReducedFees.xlsx", "skins_weekly_volumes"),
    "items_on_hold": ("7_Items_on_Hold.xlsx", "Sheet1"),
    "portfolio": ("7_Items_on_Hold.xlsx", "portfolio"),
    "selling_history": ("8_Selling_History.xlsx", "Sheet1"),
}


def excel_dir():
    """Folder where the mirrored ``.xlsx`` files live."""
    return os.environ.get("TRADING_EXCEL_DIR", _DEFAULT_EXCEL_DIR)


def excel_enabled():
    """Return ``True`` unless ``TRADING_WRITE_EXCEL`` is set to a falsey value."""
    return os.environ.get("TRADING_WRITE_EXCEL", "1").lower() not in ("0", "false", "no", "")

def create_table(table:str, params:str):
    with get_connection() as conn:
        cur = conn.execute(f'''CREATE TABLE IF NOT EXISTS "{table}" ("{params}")''',params)

def get_connection():
    """Return a SQLite connection, creating the parent folder if needed."""
    db_path = os.environ.get("TRADING_DB_PATH", DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    return sqlite3.connect(db_path)


def table_exists(table):
    """Return ``True`` if *table* exists in the database."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return cur.fetchone() is not None


def _autofit(worksheet):
    """Widen each column to fit its longest value (best-effort cosmetic)."""
    for col in worksheet.columns:
        max_length = max((len(str(cell.value)) for cell in col if cell.value is not None), default=0)
        worksheet.column_dimensions[col[0].column_letter].width = max_length + 2


def write_excel_sheet(df, filename, sheet):
    """Write *df* to ``sheet`` inside ``filename`` (under :func:`excel_dir`).

    Other sheets already present in the workbook are preserved; the target sheet
    is created or replaced. ``filename`` may be absolute to write elsewhere
    (used for the monthly archive files).
    """
    path = filename if os.path.isabs(filename) else os.path.join(excel_dir(), filename)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    if os.path.exists(path):
        writer_kwargs = {"mode": "a", "if_sheet_exists": "replace"}
    else:
        writer_kwargs = {"mode": "w"}

    with pd.ExcelWriter(path, engine="openpyxl", **writer_kwargs) as writer:
        df.to_excel(writer, sheet_name=sheet, index=False)
        _autofit(writer.book[sheet])

def delete_rows(table, column, ids):
    if not ids or not table_exists(table):
        return
    placeholders = ",".join("?" * len(ids))
    with get_connection() as conn:
        conn.execute(
            f'DELETE FROM "{table}" WHERE "{column}" IN ({placeholders})',
            list(ids),
        )
        
def replace_table(df, table, mirror_excel=True):
    """Overwrite *table* with the contents of *df* (like saving a new sheet).

    Mirrors the behaviour of the previous ``ExcelWriter`` blocks which wrote a
    brand new file every run. Column names are preserved exactly, so existing
    reader code such as ``df["Item Name"].tolist()`` keeps working.

    When ``mirror_excel`` is true and Excel mirroring is enabled (see
    :func:`excel_enabled`), the matching ``.xlsx`` sheet from
    :data:`EXCEL_REGISTRY` is updated too, keeping both stores in sync.
    """
    with get_connection() as conn:
        df.to_sql(table, conn, if_exists="replace", index=False)

    if mirror_excel and excel_enabled() and table in EXCEL_REGISTRY:
        filename, sheet = EXCEL_REGISTRY[table]
        write_excel_sheet(df, filename, sheet)


def append_table(df, table):
    """Append the rows of *df* to *table*, creating it if necessary."""
    with get_connection() as conn:
        df.to_sql(table, conn, if_exists="append", index=False)


def read_table(table):
    """Read a whole *table* into a DataFrame.

    Returns an empty DataFrame if the table does not exist yet, mirroring the
    old ``if not os.path.exists(...)`` guards.
    """
    if not table_exists(table):
        return pd.DataFrame()
    with get_connection() as conn:
        return pd.read_sql_query(f'SELECT * FROM "{table}"', conn)


def query(sql, params=()):
    """Run an arbitrary SELECT and return the result as a DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


# ---------------------------------------------------------------------------
# Tiny key/value store for single values that used to be smuggled into Excel
# cells (the "Last Sunday Change" marker row, portfolio cash / assets value).
# ---------------------------------------------------------------------------
def _ensure_meta_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")


def set_meta(key, value):
    """Store a single ``value`` under ``key`` (stored as text)."""
    with get_connection() as conn:
        _ensure_meta_table(conn)
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        conn.commit()


def get_meta(key, default=None, type=str):
    """Return the value stored under ``key`` or ``default`` if missing."""
    with get_connection() as conn:
        _ensure_meta_table(conn)
        
        if type == str:
            cur = conn.execute("SELECT value FROM meta WHERE key=?", (key,))
        elif type == float:
            cur = conn.execute("SELECT CAST(value AS REAL) FROM meta WHERE key=?", (key,))    
        else:
            print("Cannot read meta value into the type:" + type)
            
        row = cur.fetchone()
        return row[0] if row is not None else default
