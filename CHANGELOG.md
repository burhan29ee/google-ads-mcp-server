# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-13

### Added
- Initial release: a Google Ads MCP server with read AND write access,
  authenticated with the standard google-ads client configuration.
- **Read tools:** `ads_whoami`, `list_accessible_customers`, a general-purpose
  GAQL `search`, plus convenience listers for campaigns, ad groups, ads,
  budgets, and keywords, and a `campaign_performance` report.
- **Write tools:** create/update campaign budgets, create campaigns, set
  campaign status, create ad groups, set ad group status and bids, add keywords,
  and set keyword status.
- **Safety:** every write is a dry run by default — it is sent with the Google
  Ads API `validate_only` flag and only applied when called with `confirm=True`.
- Packaging as an installable console script (`google-ads-mcp-server`).

[0.1.0]: https://github.com/burhan29ee/google-ads-mcp-server/releases/tag/v0.1.0
