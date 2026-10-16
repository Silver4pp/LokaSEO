"""Penyimpanan riwayat radar di SQLite pada komputer pengguna.

Tidak ada data yang dikirim ke mana pun. Skema sengaja sederhana agar mudah
diperiksa dan dicadangkan sendiri oleh pengguna.
"""

import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'halaman',
    enabled INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    fetched_at TEXT NOT NULL,
    status INTEGER NOT NULL,
    facts TEXT NOT NULL,
    elapsed_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_snapshots_target ON snapshots(target_id, fetched_at DESC);
CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    detected_at TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    before_value TEXT,
    after_value TEXT,
    seen INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_changes_time ON changes(detected_at DESC);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# Kolom tambahan pada potret. Basis data lama tetap bisa dibuka: kolomnya
# ditambahkan saat dijalankan (lihat Store._migrasi), bukan dengan menghapus apa pun.
KOLOM_POTRET_TAMBAHAN = (
    ("sumber", "TEXT NOT NULL DEFAULT ''"),
    ("catatan", "TEXT NOT NULL DEFAULT ''"),
)


def _iso(seconds: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds or time.time()))


def _alamat_sah(url: str) -> bool:
    """Halaman biasa (http/https) atau tempat resmi Google Places (tempat:<place_id>)."""
    teks = (url or "").strip()
    if not teks:
        return False
    if teks.startswith("tempat:"):
        return len(teks.split(":", 1)[1].strip()) >= 5
    return urlsplit(teks).scheme.startswith("http")


class Store:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else config.database_path()
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self.connection.commit()
        self._migrasi()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- sasaran ------------------------------------------------------------
    def add_target(self, url: str, label: str = "", kind: str = "halaman") -> dict:
        if not _alamat_sah(url):
            raise ValueError(
                "Alamat harus dimulai dengan http:// atau https:// "
                "(atau tempat:<place_id> untuk tempat resmi Google Places)"
            )
        clean = url.strip()
        existing = self.connection.execute("SELECT * FROM targets WHERE url = ?", (clean,)).fetchone()
        if existing:
            self.connection.execute(
                "UPDATE targets SET label = ?, kind = ?, enabled = 1 WHERE id = ?",
                (label or existing["label"], kind, existing["id"]),
            )
            self.connection.commit()
            return dict(self.get_target(existing["id"]))
        cursor = self.connection.execute(
            "INSERT INTO targets (url, label, kind, enabled, added_at) VALUES (?, ?, ?, 1, ?)",
            (clean, label, kind, _iso()),
        )
        self.connection.commit()
        return dict(self.get_target(int(cursor.lastrowid)))

    def get_target(self, target_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()

    def find_target(self, url: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM targets WHERE url = ?", (url.strip(),)).fetchone()

    def targets(self, *, enabled_only: bool = False) -> list[dict]:
        query = "SELECT * FROM targets ORDER BY id"
        rows = self.connection.execute(query).fetchall()
        result = [dict(row) for row in rows]
        return [row for row in result if row["enabled"]] if enabled_only else result

    def remove_target(self, identifier: str) -> int:
        row = self.find_target(identifier)
        if row is None and identifier.isdigit():
            row = self.get_target(int(identifier))
        if row is None:
            raise KeyError(f"Sasaran tidak ditemukan: {identifier}")
        self.connection.execute("DELETE FROM targets WHERE id = ?", (row["id"],))
        self.connection.commit()
        return int(row["id"])

    def set_enabled(self, target_id: int, enabled: bool) -> None:
        self.connection.execute("UPDATE targets SET enabled = ? WHERE id = ?", (1 if enabled else 0, target_id))
        self.connection.commit()

    # -- potret -------------------------------------------------------------
    def _migrasi(self) -> None:
        """Tambahkan kolom baru pada basis data lama tanpa menghapus data."""
        ada = {row["name"] for row in self.connection.execute("PRAGMA table_info(snapshots)")}
        for nama, tipe in KOLOM_POTRET_TAMBAHAN:
            if nama not in ada:
                self.connection.execute(f"ALTER TABLE snapshots ADD COLUMN {nama} {tipe}")
        self.connection.commit()

    def latest_snapshot(self, target_id: int) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM snapshots WHERE target_id = ? ORDER BY fetched_at DESC, id DESC LIMIT 1",
            (target_id,),
        ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["facts"] = json.loads(record["facts"])
        return record

    def save_snapshot(
        self,
        target_id: int,
        status: int,
        facts: dict,
        elapsed_ms: int = 0,
        *,
        sumber: str = "",
        catatan: str = "",
    ) -> int:
        """Simpan satu potret.

        `sumber` menyebut cara halaman diambil ("permintaan-biasa", "peramban",
        "places-api") dan `catatan` menyimpan keterangan pengambilan, misalnya
        sebab rendering gagal. Keduanya disimpan supaya laporan yang dibuat
        belakangan (dari basis data) bisa jujur soal asal angkanya.
        """
        cursor = self.connection.execute(
            "INSERT INTO snapshots (target_id, fetched_at, status, facts, elapsed_ms, sumber, catatan)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (target_id, _iso(), status, json.dumps(facts, ensure_ascii=False), elapsed_ms, sumber, catatan),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def snapshots(self, target_id: int, *, since: str | None = None, limit: int | None = None) -> list[dict]:
        """Potret satu sasaran, diurutkan dari yang paling lama."""
        query = "SELECT * FROM snapshots WHERE target_id = ?"
        params: list[object] = [target_id]
        if since:
            query += " AND fetched_at >= ?"
            params.append(since)
        query += " ORDER BY fetched_at ASC, id ASC"
        if limit:
            query += " LIMIT ?"
            params.append(int(limit))
        rows = self.connection.execute(query, params).fetchall()
        result = []
        for row in rows:
            record = dict(row)
            record["facts"] = json.loads(record["facts"])
            result.append(record)
        return result

    def snapshot_count(self, target_id: int) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS total FROM snapshots WHERE target_id = ?", (target_id,)
        ).fetchone()
        return int(row["total"])

    def prune_snapshots(self, days: int = config.SNAPSHOT_RETENTION_DAYS, keep_min: int = 5) -> int:
        cutoff = time.time() - days * 86400
        rows = self.connection.execute(
            "SELECT id, target_id, fetched_at FROM snapshots ORDER BY fetched_at DESC"
        ).fetchall()
        keep: dict[int, int] = {}
        removed = 0
        for row in rows:
            target = int(row["target_id"])
            keep[target] = keep.get(target, 0) + 1
            stamp = time.mktime(time.strptime(row["fetched_at"], "%Y-%m-%dT%H:%M:%SZ"))
            if stamp < cutoff and keep[target] > keep_min:
                self.connection.execute("DELETE FROM snapshots WHERE id = ?", (row["id"],))
                removed += 1
        if removed:
            self.connection.commit()
        return removed

    # -- perubahan ----------------------------------------------------------
    def save_changes(self, target_id: int, changes: list[dict]) -> int:
        stamp = _iso()
        for row in changes:
            self.connection.execute(
                "INSERT INTO changes (target_id, detected_at, type, severity, message, before_value, after_value)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    target_id,
                    stamp,
                    row["type"],
                    row["severity"],
                    row["message"],
                    json.dumps(row.get("before"), ensure_ascii=False),
                    json.dumps(row.get("after"), ensure_ascii=False),
                ),
            )
        self.connection.commit()
        return len(changes)

    def changes(
        self,
        *,
        since: str | None = None,
        target_id: int | None = None,
        severities: tuple[str, ...] | None = None,
        limit: int = 200,
    ) -> list[dict]:
        query = (
            "SELECT c.*, t.url AS url, t.label AS label FROM changes c "
            "JOIN targets t ON t.id = c.target_id WHERE 1 = 1"
        )
        params: list = []
        if since:
            query += " AND c.detected_at >= ?"
            params.append(since)
        if target_id is not None:
            query += " AND c.target_id = ?"
            params.append(target_id)
        if severities:
            marks = ",".join("?" for _ in severities)
            query += f" AND c.severity IN ({marks})"
            params.extend(severities)
        query += " ORDER BY c.detected_at DESC, c.id DESC LIMIT ?"
        params.append(limit)
        rows = self.connection.execute(query, params).fetchall()
        result = []
        for row in rows:
            record = dict(row)
            record["before"] = json.loads(record["before_value"]) if record["before_value"] else None
            record["after"] = json.loads(record["after_value"]) if record["after_value"] else None
            result.append(record)
        return result

    def change_count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS total FROM changes").fetchone()
        return int(row["total"])

    # -- keadaan ------------------------------------------------------------
    def set_state(self, key: str, value: str) -> None:
        self.connection.execute(
            "INSERT INTO state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.connection.commit()

    def get_state(self, key: str, default: str | None = None) -> str | None:
        row = self.connection.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def stats(self) -> dict:
        return {
            "sasaran": len(self.targets()),
            "sasaran_aktif": len(self.targets(enabled_only=True)),
            "potret": self.connection.execute("SELECT COUNT(*) AS t FROM snapshots").fetchone()["t"],
            "perubahan": self.change_count(),
            "database": str(self.path),
        }
