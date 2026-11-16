class AstroplanError(Exception):
    """Base for typed domain errors mapped to HTTP status in app/api/routes.py."""


class UnknownTimezoneError(AstroplanError):
    def __init__(self, tz_name: str) -> None:
        super().__init__(f"unknown_timezone: {tz_name!r}")
        self.tz_name = tz_name


class GeocoderUnavailableError(AstroplanError):
    def __init__(self, place: str) -> None:
        super().__init__(f"geocoder_unavailable: {place!r}")
        self.place = place


class AmbiguousLocationError(AstroplanError):
    def __init__(self, place: str, candidates: list[dict[str, object]] | None = None) -> None:
        super().__init__(f"ambiguous_location: {place!r}; provide manual lat/lon")
        self.place = place
        self.candidates = candidates or []
