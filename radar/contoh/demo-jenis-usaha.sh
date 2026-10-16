#!/usr/bin/env bash
# Demo "jenis usaha sebagai kunci utama" tanpa menyentuh internet.
#
# Ceritanya begini: Anda membuat proyek di LokaSEO dengan jenis usaha
# "Kafe, kedai kopi, atau tempat makan kecil" dan kota Bogor, lalu mengunduh
# cadangan proyek. Skrip ini mengimpor cadangan itu ke radar, lalu menunjukkan
# apa yang berubah karena pilihan tadi:
#
#   - ambang rating papan reputasi mengikuti jenis usaha (4,3 untuk kafe),
#   - radar tahu mana situs sendiri dan mana pesaing,
#   - data terstruktur yang diharapkan diperiksa (CafeOrCoffeeShop dkk.),
#   - kata kunci awal jenis usaha dipakai sebagai cadangan usulan konten.
#
# Pakai:  bash contoh/demo-jenis-usaha.sh
set -euo pipefail

RADAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KERJA="$(mktemp -d)"
SITUS="$KERJA/situs"
DATA="$KERJA/data"
PORT="${PORT:-8131}"

bersihkan() {
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -rf "$KERJA"
}
trap bersihkan EXIT

mkdir -p "$SITUS"

# -- cadangan LokaSEO (bentuknya sama dengan hasil tombol "Unduh cadangan") --
cat >"$KERJA/lokaseo-cadangan.json" <<EOF
{
  "version": 1,
  "activeId": "p-kopi",
  "projects": [
    {
      "id": "p-kopi",
      "name": "Kebun Kopi Bogor",
      "domain": "127.0.0.1:$PORT",
      "city": "Bogor",
      "industry": "kafe-kedai",
      "keywords": "kedai kopi bogor",
      "articles": [],
      "checks": ["profile"],
      "audit": null,
      "auditedAt": null
    }
  ]
}
EOF

# -- halaman contoh: situs sendiri belum memakai data terstruktur yang tepat --
cat >"$SITUS/robots.txt" <<'EOF'
User-agent: *
Crawl-delay: 0
EOF

cat >"$SITUS/index.html" <<'EOF'
<!doctype html><html lang="id"><head><title>Kebun Kopi Bogor</title>
<script type="application/ld+json">{"@type":"Organization","name":"Kebun Kopi Bogor",
"aggregateRating":{"ratingValue":"4.25","reviewCount":"48"}}</script></head>
<body><h1>Kebun Kopi Bogor</h1><h2>Menu</h2></body></html>
EOF

# Pesaing dilayani server yang sama tetapi lewat nama host berbeda (localhost),
# supaya terlihat bagaimana radar memisahkan "situs sendiri" dan "pesaing".
cat >"$SITUS/pesaing.html" <<'EOF'
<!doctype html><html lang="id"><head><title>Kedai Pajajaran</title>
<script type="application/ld+json">{"@type":"CafeOrCoffeeShop","name":"Kedai Pajajaran",
"aggregateRating":{"ratingValue":"4.65","reviewCount":"470"}}</script></head>
<body><h1>Kedai Pajajaran</h1><h2>Menu Spesial</h2><h2>Layanan Katering</h2></body></html>
EOF

python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$SITUS" >/dev/null 2>&1 &
SERVER_PID=$!
sleep 2

export LOKARADAR_DATA="$DATA"
export PYTHONPATH="$RADAR_DIR"
cd "$RADAR_DIR"

echo "== 1. Impor jenis usaha dari cadangan LokaSEO =="
python3 -m lokaradar profil --dari "$KERJA/lokaseo-cadangan.json"

echo
echo "== 2. Tambah sasaran =="
python3 -m lokaradar add "http://127.0.0.1:$PORT/" --label "Situs sendiri" --kind reputasi
python3 -m lokaradar add "http://localhost:$PORT/pesaing.html" --label "Kedai Pajajaran" --kind reputasi

echo
echo "== 3. Jalankan pemantauan =="
python3 -m lokaradar run

echo
echo "== 4. Papan reputasi (ambang dari jenis usaha) =="
python3 -m lokaradar reputasi --days 30

echo
echo "== 5. Laporan =="
python3 -m lokaradar report --days 30

echo
if [[ -n "${SIMPAN:-}" ]]; then
  mkdir -p "$SIMPAN"
  cp "$(ls -t "$DATA"/laporan/laporan-*.md | head -1)" "$SIMPAN/laporan-jenis-usaha-demo.md"
  cp "$(ls -t "$DATA"/laporan/wawasan-*.json | head -1)" "$SIMPAN/wawasan-jenis-usaha-demo.json"
  echo "Contoh keluaran disalin ke: $SIMPAN"
else
  echo "Berkas hasil ada di: $DATA/laporan"
  echo "(Direktori itu dihapus saat skrip ini selesai; salin dulu bila ingin disimpan,"
  echo " atau jalankan ulang dengan SIMPAN=folder untuk menyalinnya otomatis.)"
fi
