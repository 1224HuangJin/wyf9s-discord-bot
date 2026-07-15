# Privacy Policy

Last updated: 2026-07-01

## 1. Data Collection

The Bot **does not proactively collect** personal data. During operation, it may temporarily process the following information:

### Automatically processed data

| Data type | Purpose | Storage method |
| --- | --- | --- |
| User ID / username | Permission verification, config list matching | `config.yaml` (configured by server admins) |
| Message content | Bulk cleanup (filtered by conditions) | Not stored, only read during processing |
| Channel ID | Lock schedules, subscription notifications | `schedules.yaml` / `subscribe.yaml` (IDs only, no content) |

### Logs

The Bot's runtime logs may contain user IDs and command invocation records, used for debugging and auditing. Log files are stored only locally on the machine where the Bot runs, and are not uploaded or shared with any third party.

## 2. Data Storage Location

All data is stored in local files on the server where the Bot runs (`config.yaml`, `perm.yaml`, `schedules.yaml`, `subscribe.yaml`). The Bot does not use any external database service.

## 3. Data Sharing

The Bot **does not** share any data with third parties.

## 4. Data Deletion

- User IDs in dynamic permission rules can be removed via `/perm rm`
- Channel IDs in scheduled locks can be removed via `/lock unplan`
- Server admins can remove user information from `config.yaml`
- To completely clear logs, delete the `logs/` directory

## 5. Third-Party Services

The Bot's [Emoji module](/en/modules/emoji) fetches emoji data from the configured `base_url`. The requests do not contain users' personal information.

## 6. Cookies and Tracking

The Bot does not use cookies and does not perform any form of user tracking.

## 7. Contact

For privacy-related inquiries, please [contact the developer](https://wyf9.top/c).
