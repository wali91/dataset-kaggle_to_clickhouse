# Menulis dataset Olist ke ClickHouse

Satu skrip Python, `olist_ke_clickhouse.py`, yang menyalin setiap file CSV dataset Olist
(`olistbr/brazilian-ecommerce`) menjadi satu tabel di ClickHouse. Isi data **tidak diubah**.

```
Kaggle ──download()──► data/*.csv ──pandas──► tulis_tabel() ──► ClickHouse (database olist)
```

## Cara menjalankan

```bash
python3 -m venv .venv_olise && source .venv_olise/bin/activate
python -m pip install -r requirements.txt
docker compose up -d              # jalankan ClickHouse di localhost:8123

python olist_clickhouse.py                 # download dari Kaggle lalu tulis ke ClickHouse
python olist_clickhouse.py --no-download   # pakai CSV yang sudah ada di folder data/
```

Cek hasilnya:
```bash
docker compose exec clickhouse clickhouse-client --password clickhouse -q "SHOW TABLES FROM olist"
docker compose exec clickhouse clickhouse-client --password clickhouse -q \
  "SELECT order_status, count() FROM olist.olist_orders_dataset GROUP BY order_status"
```

## Penjelasan kode

Skrip terdiri dari tiga fungsi kecil dan satu blok utama.

### 1. `download()`: mengambil data
Memakai Kaggle API untuk mengunduh dataset dan langsung mengekstrak zip-nya menjadi file CSV di folder
`data/`. Butuh `KAGGLE_USERNAME` dan `KAGGLE_KEY` di file `.env` (atau `~/.kaggle/kaggle.json`).

### 2. `tipe(kolom)`: menentukan tipe kolom
ClickHouse butuh tipe untuk setiap kolom. Fungsi ini memilihnya dari tipe kolom di pandas:

| Di pandas | Di ClickHouse |
|---|---|
| bilangan bulat | `Nullable(Int64)` |
| bilangan desimal | `Nullable(Float64)` |
| tanggal dan jam | `Nullable(DateTime)` |
| selain itu (teks) | `Nullable(String)` |

Semua tipe dibuat `Nullable` karena data Olist punya nilai kosong, misalnya pesanan yang belum diterima
tidak punya tanggal terima.

### 3. `tulis_tabel(ch, nama, df)`: menulis satu tabel
Tiga langkah:
1. **Hapus tabel lama** (`DROP TABLE IF EXISTS`), supaya data tidak dobel kalau skrip dijalankan ulang.
2. **Buat tabel baru** (`CREATE TABLE`) dengan kolom dan tipe dari fungsi `tipe()`. Mesin tabelnya
   `MergeTree`, mesin standar ClickHouse.
3. **Isi data.** Nilai kosong dari pandas (`NaN`) diubah menjadi `None` supaya tersimpan sebagai `NULL`.
   Data dikirim bertahap, 100.000 baris sekali kirim (`CHUNK`), supaya memori aman untuk file besar seperti
   `olist_geolocation_dataset` yang berisi sekitar 1 juta baris.

### 4. Blok utama: menyambungkan semuanya
1. Unduh data (kecuali pakai `--no-download`).
2. Cari file `.csv` di `data/`. Kalau tidak ada, berhenti dengan pesan jelas.
3. Konek ke ClickHouse dan buat database `olist` kalau belum ada.
4. Untuk setiap CSV: baca dengan pandas, ubah kolom tanggal menjadi tanggal-jam, lalu `tulis_tabel()`.

Kolom dianggap tanggal-jam kalau namanya mengandung `date` atau `timestamp`, atau berakhiran `_at`
(misalnya `order_purchase_timestamp`, `shipping_limit_date`, `order_approved_at`).

## Tabel yang dihasilkan

Nama tabel sama dengan nama file CSV-nya, di database `olist`:

| Tabel | Isi |
|---|---|
| `olist_orders_dataset` | pesanan, status, dan tanggal-tanggalnya |
| `olist_order_items_dataset` | barang di setiap pesanan, harga, ongkir |
| `olist_order_payments_dataset` | pembayaran setiap pesanan |
| `olist_order_reviews_dataset` | ulasan pelanggan |
| `olist_customers_dataset` | pelanggan |
| `olist_sellers_dataset` | penjual |
| `olist_products_dataset` | produk |
| `olist_geolocation_dataset` | koordinat kode pos (sekitar 1 juta baris) |
| `product_category_name_translation` | terjemahan nama kategori ke bahasa Inggris |

## Batasan yang perlu diketahui

- **Tipe kolom ditebak dari CSV.** Untuk kebutuhan analisis serius, tipe uang sebaiknya `Decimal`, bukan
  `Float64`. Versi ini sengaja sederhana. Versi dengan `Decimal` dan transformasi ada di proyek
  `olist-etl-terpisah`.
- **Tabel selalu dibuat ulang.** Menjalankan skrip lagi akan menimpa tabel lama.
- **Ulasan pelanggan** (`olist_order_reviews_dataset`) berisi teks bebas dengan koma, baris baru, dan tanda
  kutip. Pandas bisa membacanya, tetapi kolom judul dan isi ulasan sebagian besar kosong (`NULL`).

## Masalah yang sering muncul

| Gejala | Penyebab dan solusi |
|---|---|
| `Tidak ada file CSV di folder data/` | CSV belum diunduh. Jalankan tanpa `--no-download`, atau taruh CSV di `data/`. |
| Gagal autentikasi Kaggle | Isi `KAGGLE_USERNAME` dan `KAGGLE_KEY` di `.env`, atau taruh `kaggle.json` di `~/.kaggle/`. |
| `Connection refused` ke localhost:8123 | ClickHouse belum jalan. Jalankan `docker compose up -d`, lalu cek host, port, dan password di `.env`. |
| Error `pip3` saat memasang paket | Pakai `python -m pip install -r requirements.txt` di dalam virtualenv yang aktif. |
