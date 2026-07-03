from pathlib import Path

from yaml import safe_load

import utils as u

_LANG_CACHE: dict[str, dict] = {}
_DEFAULT_LANG = "zh"


def _load_lang(lang: str) -> dict:
    if lang not in _LANG_CACHE:
        path = u.get_path(f"lang/{lang}.yaml")
        if Path(path).exists():
            with open(path, "r", encoding="utf-8") as f:
                _LANG_CACHE[lang] = safe_load(f) or {}
        else:
            _LANG_CACHE[lang] = {}
    return _LANG_CACHE[lang]


def _get_nested(data: dict, key_path: str) -> str:
    parts = key_path.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict):
            return key_path
        current = current.get(part)
        if current is None:
            return key_path
    if isinstance(current, str):
        return current
    return key_path


def t(key: str, _lang: str | None = None, **kwargs) -> str:
    template = _get_nested(_load_lang(_lang or _DEFAULT_LANG), key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template
