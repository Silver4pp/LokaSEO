#!/usr/bin/env bash
# Demo LokaRadar tanpa menyentuh internet.
#
# Skrip ini menyiapkan halaman contoh di komputer sendiri (termasuk robots.txt
# yang melarang satu alamat), menjalankan dua putaran pemantauan, dan mengubah
# isi halaman di antara kedua putaran itu. Semua data disimpan di direktori
# sementara, jadi basis data radar Anda yang sebenarnya tidak tersentuh.
#
# Pakai:  bash contoh/demo-lokal.sh
set -euo pipefail

RADAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITUS="$(mktemp -d)"
DATA="$(mktemp -d)"
PORT="${PORT:-8099}"

bersihkan() {
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -rf "$SITUS" "$DATA"
}
trap bersihkan EXIT

cat >"$SITUS/robots.txt" <<'EOF'
User-agent: *
Disallow: /rahasia
Crawl-delay: 0
EOF

cat >"$SITUS/index.html" <<'EOF'
<!doctype html><html lang="id"><head><title>Kopi Bogor — Pesan Online</title>
<meta name="description" content="Kopi arabika Bogor, pesan online">
<script type="application/ld+json">{"@type":"LocalBusiness","name":"Kopi Bogor",
"aggregateRating":{"ratingValue":"4.5","reviewCount":"100"},
"offers":{"price":"150000","priceCurrency":"IDR"}}</script></head>
<body><h1>Kopi Bogor</h1><h2>Layanan Katering Kantor</h2><p>Mulai Rp 150.000</p>
<img src="a.png"></body></html>
EOF

mkdir -p "$SITUS/rahasia"
cp "$SITUS/index.html" "$SITUS/rahasia/harga.html"

# --directory dipakai (bukan subshell "cd") supaya PID yang dicatat benar-benar
# proses server; kalau memakai subshell, proses python-nya tertinggal hidup.
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$SITUS" >/dev/null 2>&1 &
SERVER_PID=$!
sleep 2

export LOKARADAR_DATA="$DATA"
export PYTHONPATH="$RADAR_DIR"
cd "$RADAR_DIR"

echo "== Menyiapkan sasaran =="
python3 -m lokaradar add "http://127.0.0.1:$PORT/" --label "Kopi Bogor (pesaing)" --kind harga
python3 -m lokaradar add "http://127.0.0.1:$PORT/rahasia/harga.html" --label "Halaman terlarang"

echo
echo "== Putaran 1: potret awal =="
python3 -m lokaradar run

echo
echo "== Mengubah halaman pesaing: harga 150.000 -> 120.000, ulasan 100 -> 130, bagian baru =="
python3 - "$SITUS/index.html" <<'PY'
import sys
import time
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = (
    text.replace('"price":"150000"', '"price":"120000"')
    .replace('"reviewCount":"100"', '"reviewCount":"130"')
    .replace("Rp 150.000", "Rp 120.000")
    .replace("</h2>", "</h2><h2>Layanan Pernikahan</h2>")
)
path.write_text(text, encoding="utf-8")
# Server bawaan Python memakai stempel waktu beresolusi detik. Beri jeda singkat
# supaya perubahan berkas terlihat sebagai versi baru, bukan jawaban "belum berubah".
time.sleep(1.2)
print("halaman diubah")
PY

echo
echo "== Putaran 2: perubahan seharusnya terdeteksi =="
python3 -m lokaradar run

echo
echo "== Laporan =="
python3 -m lokaradar report --days 30

echo
echo "Berkas hasil ada di: $DATA/laporan"
echo "(Direktori itu dihapus saat skrip ini selesai; salin dulu bila ingin disimpan.)"
