# google-ads-mcp-server

[![CI](https://github.com/burhan29ee/google-ads-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/burhan29ee/google-ads-mcp-server/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for **Google Ads** with both **read and write** access. Connect it to Claude (or any MCP client) and pull reports with GAQL, then actually manage the account — create and adjust budgets, campaigns, ad groups, bids, and keywords — in natural language, using your own Google Ads credentials.

Google's own [official Google Ads MCP server](https://github.com/googleads/google-ads-mcp) is **read-only**. This one adds the **write** side, and does it carefully.

## 🛑 Writes spend real money — how the safety guard works

Google Ads changes cost money, so **every write tool is a dry run by default.** When you call a write tool without `confirm=True`, the change is sent to the Google Ads API with its `validate_only` flag: the API checks that the change is valid **but does not apply it**, and the tool tells you it was validated only. The change is applied **only** when you call the same tool again with `confirm=True`.

That means the safe loop is always: call once to validate → review → call again with `confirm=True` to apply. New campaigns are also created **PAUSED** by default so nothing starts serving unexpectedly.

## Features

**Read**
- `ads_whoami` and `list_accessible_customers` — verify credentials and see which accounts you can reach
- `search` — run any [GAQL](https://developers.google.com/google-ads/api/docs/query/overview) query (the general-purpose read tool)
- Convenience listers: campaigns, ad groups, ads, budgets, keywords
- `campaign_performance` — impressions/clicks/cost/conversions by campaign over a date range

**Write** (dry run unless `confirm=True`)
- Create and update campaign **budgets**
- Create **campaigns** (paused Search + Manual CPC by default) and set campaign **status** (enable/pause/remove)
- Create **ad groups**, set ad group **status**, and change ad group **bids**
- Add **keywords** and set keyword **status**

## Requirements

- **Python 3.10+**
- A **Google Ads developer token**. Test tokens only work against test accounts; to read or write **real** accounts you need **Basic access**, which is a short application in the [API Center](https://developers.google.com/google-ads/api/docs/get-started/dev-token) of a manager (MCC) account.
- Credentials — either **OAuth2** (client id, client secret, refresh token) or a **service account with domain-wide delegation** (Google Workspace).
- Your manager account id as the **login customer id**.

## Google setup (one time)

1. In a Google Ads **manager (MCC) account**, open **API Center** and apply for a **developer token** with **Basic access**.
2. In the [Google Cloud Console](https://console.cloud.google.com), create a project and **enable the Google Ads API**.
3. Create **OAuth 2.0 credentials** (Desktop app) and generate a **refresh token** for an account that can access your Google Ads accounts. (Google's [OAuth desktop guide](https://developers.google.com/google-ads/api/docs/oauth/overview) walks through this; the `google-ads` library ships a helper script for the refresh token.)
4. Note your **login customer id** (the MCC id, digits only).

Alternatively, use a **service account with domain-wide delegation** on a Workspace and point the config at its key — see the [google-ads configuration docs](https://developers.google.com/google-ads/api/docs/client-libs/python/configuration).

## Install

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
git clone https://github.com/burhan29ee/google-ads-mcp-server.git
cd google-ads-mcp-server
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e .
```

Or with pip:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Configure your MCP client

The server reads the standard `GOOGLE_ADS_*` environment variables (or a `google-ads.yaml` via `GOOGLE_ADS_CONFIGURATION_FILE_PATH`). For **Claude Desktop**, edit `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "/absolute/path/to/google-ads-mcp-server/.venv/bin/python",
      "args": ["-m", "google_ads_mcp_server.server"],
      "env": {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "your-developer-token",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "1234567890",
        "GOOGLE_ADS_CLIENT_ID": "your-oauth-client-id.apps.googleusercontent.com",
        "GOOGLE_ADS_CLIENT_SECRET": "your-oauth-client-secret",
        "GOOGLE_ADS_REFRESH_TOKEN": "your-oauth-refresh-token"
      }
    }
  }
}
```

Restart the client and start with *"run ads_whoami"* to confirm access. Then try *"show my top campaigns by spend over the last 30 days"* or *"pause campaign 12345"* (which will dry-run first).

## Tool reference

| Tool | Type | What it does |
|------|------|--------------|
| `ads_whoami` | read | Show config (masked token, login id) and accessible accounts |
| `list_accessible_customers` | read | Customer resource names this login can access |
| `search` | read | Run any GAQL query |
| `list_campaigns` | read | Campaigns with status, channel, budget |
| `list_ad_groups` | read | Ad groups (optionally by campaign) |
| `list_ads` | read | Ads (optionally by ad group) |
| `list_campaign_budgets` | read | Budgets with amount and delivery |
| `list_keywords` | read | Keyword criteria (optionally by ad group) |
| `campaign_performance` | read | Per-campaign metrics over a date range |
| `create_campaign_budget` | write | Create a budget (dry run unless `confirm`) |
| `update_campaign_budget` | write | Change a budget amount (dry run unless `confirm`) |
| `create_campaign` | write | Create a paused Search campaign (dry run unless `confirm`) |
| `update_campaign_status` | write | Enable / pause / remove a campaign (dry run unless `confirm`) |
| `create_ad_group` | write | Create an ad group (dry run unless `confirm`) |
| `update_ad_group_status` | write | Enable / pause / remove an ad group (dry run unless `confirm`) |
| `update_ad_group_bid` | write | Change an ad group's max CPC (dry run unless `confirm`) |
| `add_keyword` | write | Add a keyword (dry run unless `confirm`) |
| `update_keyword_status` | write | Enable / pause / remove a keyword (dry run unless `confirm`) |

Amounts and bids are in **micros** (1,000,000 micros = 1 unit of the account currency; e.g. a $5.00 daily budget is `5000000`).

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## Security

Credentials here can change spend — treat them like production secrets. Never commit them (the `.gitignore` blocks key files, `.env`, and `google-ads.yaml`), grant least access, prefer a test account while evaluating, and keep the dry-run guard: review the `validate_only` result before re-running with `confirm=True`. See [SECURITY.md](SECURITY.md).

## Notes

- The `mcp` dependency is pinned to `>=1.2,<2`. The 2.0 SDK reorganized its API and removed `mcp.server.fastmcp`, which this server uses.
- This is an independent open-source project and is not affiliated with or endorsed by Google. It is separate from Google's official read-only [google-ads-mcp](https://github.com/googleads/google-ads-mcp).

## License

[MIT](LICENSE)
