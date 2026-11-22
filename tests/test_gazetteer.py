from pathlib import Path

from app.core.gazetteer import init_database, insert_place, prefer_country, search_places


def test_place_prefix_returns_coordinates(tmp_path: Path) -> None:
    db = tmp_path / "places.sqlite"
    conn = init_database(db)
    insert_place(
        conn,
        geoname_id=1,
        name="Pune",
        ascii_name="Pune",
        alternate_names="Poona",
        country_code="IN",
        country_name="India",
        admin1="Maharashtra",
        latitude=18.51957,
        longitude=73.85535,
        timezone="Asia/Kolkata",
        population=3124458,
    )
    insert_place(
        conn,
        geoname_id=2,
        name="Pune",
        ascii_name="Pune",
        alternate_names="",
        country_code="XX",
        country_name="Elsewhere",
        admin1="",
        latitude=1.0,
        longitude=2.0,
        timezone="UTC",
        population=10,
    )
    conn.commit()
    conn.close()

    hits = search_places(str(db), "Pun", limit=5)
    assert hits[0].name == "Pune"
    assert hits[0].latitude == 18.51957
    assert hits[0].display_name == "Pune, Maharashtra, India"
    chosen = prefer_country(hits, "India")
    assert chosen[0].country == "India"
    assert search_places("", "Pune") == []
