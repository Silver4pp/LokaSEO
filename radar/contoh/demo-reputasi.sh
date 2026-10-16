#!/usr/bin/env bash
# Demo papan reputasi lokal tanpa menyentuh internet.
#
# Skrip ini membangun riwayat contoh selama 30 hari untuk tiga usaha (usaha
# sendiri dan dua pesaing), lalu menjalankan perintah `reputasi` dan `report`.
#
# Riwayat di sini **simulasi** supaya hasilnya langsung terlihat: pada pemakaian
# sungguhan, riwayat terbentuk dari pemeriksaan berkala (`run`) yang menyimpan
# angka agregat apa adanya. Semua data disimpan di direktori sementara.
#
# Pakai:  bash contoh/demo-reputasi.sh
set -euo pipefail

RADAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$(mktemp -d)"
trap 'rm -rf "$DATA"' EXIT

export LOKARADAR_DATA="$DATA"
export PYTHONPATH="$RADAR_DIR"
cd "$RADAR_DIR"

echo "== Membangun riwayat contoh 30 hari =="
python3 - "$DATA" <<'PY'
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lokaradar.store import Store

# (label, rating tiap minggu, jumlah ulasan tiap minggu)
USAHA = [
    ("Kopi Bogor (usaha saya)", "https://kopi-bogor.example/", [4.30, 4.42, 4.55, 4.61], [96, 104, 112, 121]),
    ("Kedai Pajajaran", "https://kedai-pajajaran.example/", [4.68, 4.68, 4.66, 4.65], [410, 431, 455, 470]),
    ("Warung Sempurna", "https://warung-sempurna.example/", [4.80, 4.66, 4.51, 4.38], [88, 92, 97, 99]),
]


def stamp(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


store = Store()
for label, url, ratings, counts in USAHA:
    target = store.add_target(url, label, "reputasi")
    for minggu, (rating, count) in enumerate(zip(ratings, counts)):
        days_ago = 28 - minggu * 9
        snapshot_id = store.save_snapshot(
            int(target["id"]),
            200,
            {"title": label, "rating": {"value": rating, "count": count, "scale": 5}},
        )
        store.connection.execute("UPDATE snapshots SET fetched_at = ? WHERE id = ?", (stamp(days_ago), snapshot_id))
store.connection.commit()
store.close()
print("3 usaha × 4 titik riwayat disiapkan")
PY

echo
echo "== Papan reputasi =="
python3 -m lokaradar reputasi --days 30 --min-rating 4.6

echo
echo "== Laporan =="
python3 -m lokaradar report --days 30

echo
echo "Berkas hasil ada di: $DATA/laporan"
echo "(Direktori itu dihapus saat skrip ini selesai; salin dulu bila ingin disimpan.)"
