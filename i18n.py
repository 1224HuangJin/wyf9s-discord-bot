from pathlib import Path

import discord
from discord import app_commands
from yaml import safe_load

import utils as u

_LANG_CACHE: dict[str, dict] = {}
_DEFAULT_LANG = "zh"

# Language shown as the base (fallback) value for Discord-registered command
# metadata (names/descriptions). Discord uses this whenever a user's client
# locale has no matching localization.
_BASE_LANG = "en"

# Languages we ship translations for.
SUPPORTED_LANGS = ("zh", "en")


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


# ========== Runtime resolution helpers ==========


def lang_of(source, lang_store) -> str:
    """
    从 Interaction / Context 解析应使用的语言

    :param source: discord.Interaction 或 commands.Context
    :param lang_store: LangStore 实例 (可为 None)
    :return: 语言代码 (如 "zh" / "en")
    """
    if lang_store is None:
        return _DEFAULT_LANG
    if isinstance(source, discord.Interaction):
        user_id = source.user.id
    else:
        author = getattr(source, "author", None)
        user_id = getattr(author, "id", 0)
    guild = getattr(source, "guild", None)
    guild_id = guild.id if guild else None
    return lang_store.resolve(user_id, guild_id)


# ========== Discord command localization ==========


def ls(key: str) -> app_commands.locale_str:
    """
    构造一个用于斜杠命令名称/描述的可本地化字符串

    默认(注册)值使用 `_BASE_LANG` (英文), 其余 Discord 客户端语言由
    `I18nTranslator` 在同步时按 `key` 查表翻译.

    :param key: lang 文件中的键 (如 "tools.cmd_random_desc")
    """
    return app_commands.locale_str(t(key, _BASE_LANG), key=key)


_LOCALE_TO_LANG: dict[discord.Locale, str] = {
    discord.Locale.american_english: "en",
    discord.Locale.british_english: "en",
    discord.Locale.chinese: "zh",
    discord.Locale.taiwan_chinese: "zh",
}


def discord_locale_to_lang(locale: discord.Locale) -> str | None:
    """将 Discord 客户端 locale 映射到本项目支持的语言, 无匹配返回 None"""
    return _LOCALE_TO_LANG.get(locale)


class I18nTranslator(app_commands.Translator):
    """
    基于 lang 文件的斜杠命令元数据翻译器

    仅翻译通过 `ls()` 创建、带有 `key` extra 的 locale_str;
    对于无对应翻译或使用基准语言(英文)的 locale, 返回 None 以回退到默认值.
    """

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContext,
    ) -> str | None:
        key = string.extras.get("key")
        if not key:
            return None
        lang = discord_locale_to_lang(locale)
        if lang is None or lang == _BASE_LANG:
            # No localization needed; Discord falls back to the base message.
            return None
        text = t(key, lang)
        if text == key:
            # Missing translation -> fall back to base message.
            return None
        return text
