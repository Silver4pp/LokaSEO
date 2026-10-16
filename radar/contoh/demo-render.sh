#!/usr/bin/env bash
# Demo rendering: halaman yang isinya dibuat oleh JavaScript.
#
# Banyak situs kecil zaman sekarang mengirim HTML kosong lalu mengisi isinya
# lewat JavaScript. Permintaan biasa hanya melihat kerangka halaman — persis
# temuan uji Bogor pada fdcdentalclinic.co.id yang hanya terbaca 3 kata.
# Skrip ini menyiapkan satu situs lokal seperti itu, lalu memperlihatkan tiga
# perilaku radar terhadapnya:
#
#   1. --render tidak   → halaman terbaca hampir kosong (inilah masalahnya)
#   2. --render auto    → halaman tipis diambil ulang dengan peramban
#   3. --render selalu  → langsung peramban, tanpa permintaan biasa
#
# Pakai:  bash contoh/demo-render.sh
#
# Memerlukan peramban Playwright sekali saja: `scrapling install`
# (atau `playwright install chromium`).
set -euo pipefail

RADAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITUS="$(mktemp -d)"
DATA="$(mktemp -d)"
PORT="${PORT:-8177}"

export LOKARADAR_DATA="$DATA"
export PYTHONPATH="$RADAR_DIR"
cd "$RADAR_DIR"

cat > "$SITUS/index.html" <<'HTML'
<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <title>Kopi Ranah — Kedai Kopi Bogor</title>
  <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "CafeOrCoffeeShop", "name": "Kopi Ranah",
     "aggregateRating": {"@type": "AggregateRating", "ratingValue": 4.7, "reviewCount": 158}}
  </script>
</head>
<body>
  <!-- Kerangka khas aplikasi JavaScript: isi <div id="root"> baru terisi setelah skrip jalan. -->
  <div id="root">Memuat…</div>
  <script>
    // Isi halaman hanya muncul setelah JavaScript jalan — inilah yang tidak
    // terlihat oleh permintaan HTTP biasa.
    document.getElementById('root').innerHTML = [
      '<h1>Kopi Ranah — kedai kopi di Bogor</h1>',
      '<p>Kami menyeduh kopi arabika dari Puncak, Gunung Salak, dan Sukabumi.',
      'Menu andalan: kopi susu gula aren, manual brew V60, dan es kopi kelapa.</p>',
      '<h2>Daftar harga</h2>',
      '<ul>',
      '<li>Kopi susu gula aren Rp 24.000</li>',
      '<li>Manual brew V60 Rp 32.000</li>',
      '<li>Es kopi kelapa Rp 28.000</li>',
      '<li>Roti bakar srikaya Rp 18.000</li>',
      '</ul>',
      '<p>Buka setiap hari 08.00-22.00 di Jalan Pajajaran, Bogor Utara.',
      'Menerima pesan antar lewat WhatsApp dan ojek daring. Ada tempat duduk luar,',
      'mushala, dan parkir motor yang luas. Cocok untuk kerja jarak jauh karena',
      'tersedia stop kontak dan wifi 50 Mbps.</p>',
    ].join('');
  </script>
</body>
</html>
HTML

python3 -m http.server --directory "$SITUS" --bind 127.0.0.1 "$PORT" > /dev/null 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true; rm -rf "$SITUS" "$DATA"' EXIT
sleep 1

URL="http://127.0.0.1:$PORT/"

echo "== 1. Tanpa peramban: hanya kerangka halaman yang terlihat =="
python3 -m lokaradar --render tidak scrape "$URL"

echo
echo "== 2. --render auto: halaman tipis diambil ulang dengan peramban =="
if python3 -m lokaradar --render auto scrape "$URL" | tail -3; then :; fi

echo
echo "== 3. Alur radar lengkap dengan mode auto =="
python3 -m lokaradar add "$URL" --label "Kopi Ranah" --kind harga
python3 -m lokaradar run
python3 -m lokaradar report --out "$DATA/laporan" > /dev/null
echo
echo "--- isi laporan (bagian sasaran) ---"
awk '/^## Kopi Ranah/ {tampil=1} tampil && /^## /&&!/^## Kopi Ranah/ {tampil=0} tampil' \
  "$(ls -t "$DATA"/laporan/laporan-*.md | head -1)" | sed '/^$/d' | head -10
echo
echo "--- usulan untuk LokaSEO ---"
python3 -c "
import json,glob
berkas = sorted(glob.glob('$DATA/laporan/wawasan-*.json'))[-1]
paket = json.load(open(berkas))
for baris in paket['lokaseo']['catatan']:
    print('·', baris)
"

if [[ -n "${SIMPAN:-}" ]]; then
  mkdir -p "$SIMPAN"
  cp "$(ls -t "$DATA"/laporan/laporan-*.md | head -1)" "$SIMPAN/laporan-render-demo.md"
  cp "$(ls -t "$DATA"/laporan/wawasan-*.json | head -1)" "$SIMPAN/wawasan-render-demo.json"
  echo
  echo "Contoh keluaran disalin ke: $SIMPAN"
fi
