"""Menjalankan perintah LokaRadar dengan jawaban Places API tiruan.

Dipakai oleh `contoh/demo-places.sh` supaya seluruh alur Places API bisa
diperlihatkan tanpa kunci dan **tanpa satu pun permintaan ke Google**. Pada
pemakaian sungguhan, perintah dijalankan seperti biasa (`python -m lokaradar …`)
dengan `LOKARADAR_PLACES_KEY` berisi kunci milik Anda.

Setel `PUTARAN=2` untuk meniru keadaan setelah rating pesaing berubah.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lokaradar import places  # noqa: E402
from lokaradar.cli import main  # noqa: E402

CARI = {
    "places": [
        {
            "id": "ChIJkliniksehatbogor",
            "displayName": {"text": "Klinik Gigi Sehat Bogor"},
            "formattedAddress": "Jl. Raya Pajajaran No. 12, Bogor Utara, Kota Bogor",
            "rating": 4.6,
            "userRatingCount": 214,
            "websiteUri": "https://kliniksehat.example/",
        },
        {
            "id": "ChIJklinikgigibogor2",
            "displayName": {"text": "Klinik Gigi Bogor Selatan"},
            "formattedAddress": "Jl. Tajur No. 8, Bogor Selatan, Kota Bogor",
            "rating": 4.1,
            "userRatingCount": 57,
        },
    ]
}

DETAIL = {
    "ChIJkliniksehatbogor": {
        "id": "ChIJkliniksehatbogor",
        "displayName": {"text": "Klinik Gigi Sehat Bogor"},
        "formattedAddress": "Jl. Raya Pajajaran No. 12, Bogor Utara, Kota Bogor",
        "rating": 4.6,
        "userRatingCount": 214,
    },
    "ChIJklinikgigibogor2": {
        "id": "ChIJklinikgigibogor2",
        "displayName": {"text": "Klinik Gigi Bogor Selatan"},
        "formattedAddress": "Jl. Tajur No. 8, Bogor Selatan, Kota Bogor",
        "rating": 4.1,
        "userRatingCount": 57,
    },
}

PUTARAN = int(os.environ.get("PUTARAN", "1"))
PERUBAHAN = {"ChIJkliniksehatbogor": {"rating": 4.3, "userRatingCount": 239}}


def loader(spec, timeout):  # noqa: ARG001 - tanda tangan pemanggil Places
    """Jawaban tiruan. Tidak pernah menyentuh jaringan."""
    if spec.url.endswith(":searchText"):
        return 200, json.dumps(CARI)
    place_id = spec.url.rsplit("/", 1)[-1]
    data = dict(DETAIL.get(place_id, {}))
    if PUTARAN >= 2 and place_id in PERUBAHAN:
        data.update(PERUBAHAN[place_id])
    return 200, json.dumps(data)


places._default_loader = loader
raise SystemExit(main(sys.argv[1:]))
