"""Build the worldwide place index used for birth-place suggestions.

GeoNames publishes the source dumps. The default extract is every populated
place with at least 500 residents (cities500). Pass ``--dataset allCountries``
for the full GeoNames dump, filtered to populated places only.

    python scripts/extract_places.py
    python scripts/extract_places.py --dataset allCountries --output data/places.sqlite
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.gazetteer import init_database, insert_place  # noqa: E402

DUMPS = {
    "cities500": "https://download.geonames.org/export/dump/cities500.zip",
    "cities5000": "https://download.geonames.org/export/dump/cities5000.zip",
    "allCountries": "https://download.geonames.org/export/dump/allCountries.zip",
}
COUNTRY_INFO = "https://download.geonames.org/export/dump/countryInfo.txt"
ADMIN1 = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "astroplan-place-extract/3.6"})
    with urlopen(request, timeout=120) as response:
        return response.read()


def _countries(payload: bytes) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in payload.decode("utf-8", errors="replace").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) > 4:
            found[columns[0]] = columns[4]
    return found


def _admin1(payload: bytes) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in payload.decode("utf-8", errors="replace").splitlines():
        columns = line.split("\t")
        if len(columns) > 1:
            found[columns[0]] = columns[1]
    return found


def _rows(payload: bytes):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = next(item for item in archive.namelist() if item.endswith(".txt"))
        with archive.open(name) as handle:
            for raw in handle:
                yield raw.decode("utf-8", errors="replace").rstrip("\n")


def build(dataset: str, output: Path) -> int:
    print(f"Downloading {dataset} and country tables...")
    countries = _countries(_download(COUNTRY_INFO))
    admins = _admin1(_download(ADMIN1))
    dump = _download(DUMPS[dataset])
    if output.exists():
        output.unlink()
    conn = init_database(output)
    kept = 0
    try:
        for line in _rows(dump):
            columns = line.split("\t")
            if len(columns) < 19 or columns[6] != "P":
                continue
            country_code = columns[8]
            admin_key = f"{country_code}.{columns[10]}"
            alternates = ",".join(columns[3].split(",")[:8])
            population = int(columns[14] or "0")
            insert_place(
                conn,
                geoname_id=int(columns[0]),
                name=columns[1],
                ascii_name=columns[2],
                alternate_names=alternates,
                country_code=country_code,
                country_name=countries.get(country_code, country_code),
                admin1=admins.get(admin_key, ""),
                latitude=float(columns[4]),
                longitude=float(columns[5]),
                timezone=columns[17],
                population=population,
            )
            kept += 1
            if kept % 50000 == 0:
                conn.commit()
                print(f"  {kept} places")
        conn.commit()
    finally:
        conn.close()
    print(f"Wrote {kept} places to {output}")
    return kept


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a worldwide place index")
    parser.add_argument(
        "--dataset",
        choices=sorted(DUMPS),
        default="cities500",
        help="cities500 is every populated place with 500 or more residents",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "places.sqlite")
    args = parser.parse_args()
    build(args.dataset, args.output)


if __name__ == "__main__":
    main()
