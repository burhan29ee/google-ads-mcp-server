# Contributing

Thanks for your interest in improving **google-ads-mcp-server**! Contributions of
all kinds are welcome — bug reports, feature requests, docs, and code.

## Development setup

Requires Python 3.10+.

```bash
git clone https://github.com/burhan29ee/google-ads-mcp-server.git
cd google-ads-mcp-server
python -m venv .venv && source .venv/bin/activate   # or: uv venv --python 3.12 .venv
pip install -e ".[dev]"                              # installs the package + pytest + ruff
```

## Running checks

```bash
ruff check .     # lint
pytest -q        # tests
```

The smoke tests import the package and exercise pure helpers — they do **not**
require Google Ads credentials.

## Testing against live Google Ads (optional)

This touches accounts that spend money. Always test on a throwaway/scratch
account or a test manager account, and rely on the built-in dry run: every write
tool sends `validate_only=True` unless you pass `confirm=True`, so you can verify
a change is valid before applying it. Never point `confirm=True` at a production
account while developing.

## Pull requests

1. Open an issue first for anything non-trivial so we can agree on the approach.
2. Keep changes focused; add or update a test when it makes sense.
3. Run `ruff check .` and `pytest` before pushing.
4. Update `CHANGELOG.md` under an "Unreleased" heading.
5. Never commit credentials — the `.gitignore` blocks key files, `.env`,
   `google-ads.yaml`, and `*.json` (except the example config).

## Notes for maintainers

- The `mcp` dependency is pinned to `>=1.2,<2`: the 2.0 SDK reorganized its API
  and removed `mcp.server.fastmcp`, which this server uses.
- The client is built lazily so the package imports without credentials.
- Writes use each service's `mutate_*` method with `validate_only` toggled by the
  tool's `confirm` argument; updates set an `update_mask` via
  `protobuf_helpers.field_mask`.
