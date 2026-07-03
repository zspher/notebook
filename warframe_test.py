# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: cwwwh4v7kmxa5494jn85vzxzzm6crlwr-dev-env
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Warframe stuff & data
#
# answers the ff. questions:
# 1. whats the most expensive arcane in warframe.market
#    - list of arcanes
#    - call warframe.market api w/ timeouts to follow rate limit
#    - get a list of prices from warframe.market
#    - maybe use sqlite to cache request results
#
# - resources
#   - [warframe.market api docs](https://42bytes.notion.site/WFM-Api-v2-Documentation-5d987e4aa2f74b55a80db1a09932459d)

# %%
import dis
import requests
import pandas as pd
import sqlite3
from ratelimit import limits, sleep_and_retry
from datetime import datetime, timezone, timedelta
from IPython.display import display

WARFRAME_MARKET_API = "https://api.warframe.market/v2"
WARFRAME_MARKET_API_V1 = "https://api.warframe.market/v1"


def get_items():
    return requests.get(f"{WARFRAME_MARKET_API}/items").json()["data"]


@sleep_and_retry
@limits(calls=3, period=1)
def get_stats(item):
    return requests.get(f"{WARFRAME_MARKET_API_V1}/items/{item}/statistics").json()[
        "payload"
    ]


# %%
with sqlite3.connect("./assets/data.db") as conn:
    c = conn.cursor()

    # c.execute("DROP TABLE IF EXISTS arcanes;")
    # c.execute("DROP TABLE IF EXISTS statistics;")

    c.execute("""
        CREATE TABLE IF NOT EXISTS arcanes (
            name VARCHAR(255) PRIMARY KEY,
            max_rank int,
            rarity VARCHAR(255),
            type VARCHAR(255)
        );
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name int,
            date DATETIME,
            volume INT,
            min_price INT,
            max_price INT,
            open_price INT,
            closed_price INT,
            mod_rank INT,
            FOREIGN KEY (item_name) REFERENCES arcanes(name)
        );
    """)

    conn.commit()


# %%
def convert_to_slug(name: str):
    sep = "-" if "-" in name else "_"
    return name.replace(" ", sep).lower()


with sqlite3.connect("./assets/data.db") as conn:
    res = pd.read_json("./assets/arcanes.json", orient="index")
    res[["Name", "MaxRank", "Rarity", "Type"]].rename(
        columns={
            "Name": "name",
            "MaxRank": "max_rank",
            "Rarity": "rarity",
            "Type": "type",
        }
    ).assign(name=lambda df: df["name"].map(convert_to_slug)).to_sql(
        "arcanes", conn, if_exists="replace", index=False
    )

# %%

# with sqlite3.connect("./assets/data.db") as conn:
#     res = pd.read_sql_query("SELECT name FROM arcanes;", conn)
#     for i, arcane in res.iterrows():
#         data = get_stats(arcane['name'])
#         statistics_closed = pd.DataFrame(data["statistics_closed"]["90days"])
#         statistics_closed[["datetime", "volume", "min_price", "max_price", "open_price", "closed_price", "mod_rank"]].assign(item_name=arcane["name"]).to_sql(
#             "statistics", conn, if_exists="append", index=False
#         )


# %%
with sqlite3.connect("./assets/data.db") as conn:
    res = pd.read_sql_query("SELECT * FROM statistics;", conn)

    now = (
        (datetime.now(timezone.utc) - timedelta(days=1))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat(timespec="milliseconds")
    )
    dt = (
        res.query(f"datetime == '{now}' & mod_rank == 0 & volume > 100")
        .sort_values(["closed_price", "volume"], ascending=False)
        .head(20)
    )
    display(dt)
