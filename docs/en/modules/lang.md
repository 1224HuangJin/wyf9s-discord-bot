# Localization (lang)

Switch the language preference of a user / server. All user-facing text of the bot supports localization (i18n).

- **Config key**: none (this module is always enabled)
- **Source files**: `cogs/lang.py`, `i18n.py`, `lang_store.py`, `lang/*.yaml`

## Language Resolution Priority

For each message, the bot resolves the language to use in the following priority order:

1. **User preference** — the personal language the user set via `/lang`
2. **Server preference** — the language a server administrator set via `/lang scope:server`
3. **Default language** — `zh` (Simplified Chinese)

Preferences are persisted to `lang_settings.yaml` (auto-generated).

## Commands

### `/lang` — Set / view language preference

| Item | Description |
| --- | --- |
| Permission | Everyone (`scope:server` requires the "Manage Server" permission or a config admin) |
| Parameter | `lang` (optional, `zh` / `en`, leave empty to view the current setting), `scope` (optional, `user` (default) / `server`) |

- `/lang lang:en` — Set **your** language to English.
- `/lang lang:zh scope:server` — Set **this server's** default language to Chinese (requires manage permission).
- `/lang` — View your current language preference.
- `/lang scope:server` — View this server's language preference.

## Coverage

Localization is divided into two types of text, handled differently:

| Type | Example | Localization method |
| --- | --- | --- |
| **Runtime messages** | Command replies, errors, audit logs, anti-spam notices | Resolved **per-user / per-server** by the priority above |
| **Slash command / parameter descriptions** | The descriptive text in Discord's command panel | Via discord.py command localization (`locale_str` + `Translator`), displayed according to the user's **Discord client language** |

> Command **names** (e.g. `/random`) stay unchanged and are not localized.

## Supported Languages

| Code | Language | Discord Locale |
| --- | --- | --- |
| `zh` | Simplified Chinese (default) | `zh-CN` / `zh-TW` |
| `en` | English | `en-US` / `en-GB` |

## Adding a Language

1. Copy `lang/zh.yaml` to `lang/<code>.yaml` and translate all its values (keeping the keys unchanged).
2. Add `<code>` to `SUPPORTED_LANGS` in `i18n.py`.
3. If you want Discord client language linkage, add the locale mapping in `_LOCALE_TO_LANG` in `i18n.py`.

> `lang/zh.yaml` and `lang/en.yaml` must keep **exactly the same keys**; when adding new text, both files must be updated in sync.
