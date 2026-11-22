"""Local worldwide place index built by scripts/extract_places.py."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"\w+", flags=re.UNICODE)


@dataclass(frozen=True)
class PlaceHit:
    name: str
    country: str
    admin1: str
    latitude: float
    longitude: float
    timezone: str
    population: int

    @property
    def display_name(self) -> str:
        parts = [self.name]
        if self.admin1 and self.admin1.casefold() != self.name.casefold():
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


def init_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            ascii_name TEXT NOT NULL,
            country_code TEXT NOT NULL,
            country_name TEXT NOT NULL,
            admin1 TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timezone TEXT NOT NULL,
            population INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS places_fts USING fts5(
            name, ascii_name, alternate_names, country_name, admin1,
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    return conn


def insert_place(
    conn: sqlite3.Connection,
    *,
    geoname_id: int,
    name: str,
    ascii_name: str,
    alternate_names: str,
    country_code: str,
    country_name: str,
    admin1: str,
    latitude: float,
    longitude: float,
    timezone: str,
    population: int,
) -> None:
    conn.execute(
        """
        INSERT INTO places (
            id, name, ascii_name, country_code, country_name, admin1,
            latitude, longitude, timezone, population
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            geoname_id,
            name,
            ascii_name,
            country_code,
            country_name,
            admin1,
            latitude,
            longitude,
            timezone,
            population,
        ),
    )
    conn.execute(
        """
        INSERT INTO places_fts (
            rowid, name, ascii_name, alternate_names, country_name, admin1
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (geoname_id, name, ascii_name, alternate_names, country_name, admin1),
    )


def _match_query(text: str) -> str:
    tokens = _TOKEN.findall(text)[:6]
    if not tokens:
        return ""
    return " AND ".join(f'"{token}"*' for token in tokens)


def search_places(db_path: str, query: str, limit: int = 8) -> list[PlaceHit]:
    path = Path(db_path)
    if not db_path or not path.is_file():
        return []
    match = _match_query(query)
    if not match:
        return []
    bounded = min(max(limit, 1), 8)
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            SELECT p.name, p.country_name, p.admin1, p.latitude, p.longitude,
                   p.timezone, p.population
            FROM places_fts
            JOIN places p ON p.id = places_fts.rowid
            WHERE places_fts MATCH ?
            ORDER BY p.population DESC
            LIMIT ?
            """,
            (match, bounded),
        ).fetchall()
    return [
        PlaceHit(
            name=row[0],
            country=row[1],
            admin1=row[2],
            latitude=float(row[3]),
            longitude=float(row[4]),
            timezone=row[5],
            population=int(row[6]),
        )
        for row in rows
    ]


def prefer_country(hits: list[PlaceHit], country: str | None) -> list[PlaceHit]:
    if not country:
        return hits
    wanted = country.casefold()
    matched = [hit for hit in hits if hit.country.casefold() == wanted]
    return matched or hits
