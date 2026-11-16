from __future__ import annotations

import json
from pathlib import Path

from app.api.schemas import LanguageCode
from app.interpretation.errors import MissingI18nKeyError


class Catalog:
    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._cache: dict[LanguageCode, dict[str, str]] = {}

    def _load(self, lang: LanguageCode) -> dict[str, str]:
        if lang not in self._cache:
            self._cache[lang] = json.loads((self._dir / f"{lang}.json").read_text(encoding="utf-8"))
        return self._cache[lang]

    def get(self, key: str, lang: LanguageCode) -> str:
        cat = self._load(lang)
        if key not in cat:
            raise MissingI18nKeyError(f"{lang}: {key}")
        return cat[key]

    def format(self, key: str, lang: LanguageCode, **kwargs: object) -> str:
        return self.get(key, lang).format(**kwargs)

    def glossary(self, lang: LanguageCode) -> dict[str, str]:
        cat = self._load(lang)
        return {k.removeprefix("tooltip."): v for k, v in cat.items() if k.startswith("tooltip.")}
