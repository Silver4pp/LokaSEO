#!/usr/bin/env bash
# Demo alur Google Places API tanpa kunci dan tanpa internet.
#
# Temuan uji Bogor: hampir tidak ada usaha lokal yang menulis rating di situsnya
# sendiri (1 dari 7). Karena itu radar menyediakan jalur resmi Places API. Skrip
# ini memperlihatkan seluruh alurnya memakai **jawaban tiruan** lewat
# `contoh/places-tiruan.py` — tidak ada permintaan ke Google, tidak ada kuota
# yang terpakai.
#
# Pakai:  bash contoh/demo-places.sh
set -euo pipefail

RADAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$(mktemp -d)"
trap 'rm -rf "$DATA"' EXIT

export LOKARADAR_DATA="$DATA"
export PYTHONPATH="$RADAR_DIR"
export LOKARADAR_PLACES_KEY="kunci-tiruan-untuk-demo"
cd "$RADAR_DIR"

jalankan() { python3 contoh/places-tiruan.py "$@"; }

echo "== 1. Status: kesiapan kunci Places =="
jalankan status

echo
echo "== 2. Profil dari jenis usaha (klinik: rating dianggap penting) =="
jalankan profil --jenis klinik-kesehatan --nama "Klinik Gigi Sehat Bogor" \
  --kota Bogor --situs kliniksehat.example

echo
echo "== 3. Cari place_id (Places Text Search, jawaban tiruan) =="
jalankan cari "Klinik Gigi" --kota Bogor --tambah 1

echo
echo "== 4. Tambah pesaing sebagai sasaran rating =="
jalankan add tempat:ChIJklinikgigibogor2 --label "Klinik Gigi Bogor Selatan" --kind reputasi

echo
echo "== 5. Putaran pertama: ambil angka resmi =="
PUTARAN=1 jalankan run

echo
echo "== 6. Rating pesaing berubah (putaran kedua) =="
PUTARAN=2 jalankan run

echo
echo "== 7. Papan reputasi (ambang 4,4 dari jenis usaha klinik) =="
PUTARAN=2 jalankan reputasi --days 30 --out "$DATA/laporan"

echo
echo "== 8. Laporan =="
PUTARAN=2 jalankan report --days 30

echo
if [[ -n "${SIMPAN:-}" ]]; then
  mkdir -p "$SIMPAN"
  cp "$(ls -t "$DATA"/laporan/laporan-*.md | head -1)" "$SIMPAN/laporan-places-demo.md"
  cp "$(ls -t "$DATA"/laporan/reputasi-*.md | head -1)" "$SIMPAN/papan-places-demo.md"
  cp "$(ls -t "$DATA"/laporan/wawasan-*.json | head -1)" "$SIMPAN/wawasan-places-demo.json"
  echo "Contoh keluaran disalin ke: $SIMPAN"
else
  echo "Berkas hasil ada di: $DATA"
  echo "(Direktori itu dihapus saat skrip ini selesai; jalankan dengan SIMPAN=folder untuk menyalinnya.)"
fi
echo
echo "Pada pemakaian sungguhan, ganti kunci tiruan dengan kunci Anda sendiri"
echo "(LOKARADAR_PLACES_KEY). Pencarian memakai SKU Text Search dan detail tempat"
echo "memakai SKU Place Details pada kuota Google Cloud Anda."
