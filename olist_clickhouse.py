"""Tulis dataset Olist (Kaggle) ke ClickHouse. Satu file CSV = satu tabel.

    python olist_ke_clickhouse.py                  # download dari Kaggle, lalu tulis ke ClickHouse
    python olist_ke_clickhouse.py --no-download    # pakai CSV yang sudah ada di folder data/
"""
import argparse
import os
from pathlib import Path

import clickhouse_connect
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
DATA_DIR = Path("data")
DATABASE = os.getenv("CLICKHOUSE_DATABASE", "olist")
CHUNK = 100_000   # jumlah baris yang dikirim sekali jalan


# 1. EXTRACT: unduh semua file CSV dari Kaggle ke folder data/
def download():
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files("olistbr/brazilian-ecommerce", path=str(DATA_DIR), unzip=True)


# 2. Tentukan tipe kolom ClickHouse dari tipe kolom pandas
def tipe(kolom: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(kolom):
        return "Nullable(Int64)"
    if pd.api.types.is_float_dtype(kolom):
        return "Nullable(Float64)"
    if pd.api.types.is_datetime64_any_dtype(kolom):
        return "Nullable(DateTime)"
    return "Nullable(String)"


# 3. LOAD: satu file CSV -> satu tabel di ClickHouse
def tulis_tabel(ch, nama: str, df: pd.DataFrame):
    kolom = ", ".join(f"`{c}` {tipe(df[c])}" for c in df.columns)
    ch.command(f"DROP TABLE IF EXISTS `{DATABASE}`.`{nama}`")
    ch.command(f"CREATE TABLE `{DATABASE}`.`{nama}` ({kolom}) ENGINE = MergeTree ORDER BY tuple()")

    df = df.astype(object).where(df.notna(), None)   # nilai kosong (NaN) -> None agar jadi NULL
    for i in range(0, len(df), CHUNK):               # kirim bertahap supaya memori aman
        ch.insert(f"`{DATABASE}`.`{nama}`", df.iloc[i:i + CHUNK].values.tolist(),
                  column_names=list(df.columns))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    if not ap.parse_args().no_download:
        download()

    files = sorted(DATA_DIR.glob("*.csv"))
    if not files:
        raise SystemExit("Tidak ada file CSV di folder data/. Jalankan tanpa --no-download.")

    ch = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse"),
    )
    ch.command(f"CREATE DATABASE IF NOT EXISTS `{DATABASE}`")

    for f in files:
        df = pd.read_csv(f)
        # kolom bernama "...date...", "...timestamp..." atau "..._at" dibaca sebagai tanggal-jam
        for c in df.columns:
            if "date" in c or "timestamp" in c or c.endswith("_at"):
                df[c] = pd.to_datetime(df[c], errors="coerce")
        tulis_tabel(ch, f.stem, df)
        print(f"{f.name} -> {DATABASE}.{f.stem}: {len(df):,} baris")
