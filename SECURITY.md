# Security Policy

## Supported versions

This project is pre-1.0; the latest release on `main` is supported.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, use
GitHub's private vulnerability reporting (the "Report a vulnerability" button
under the repository's **Security** tab). We aim to acknowledge reports within a
few days.

## Handling credentials and spend

This server holds credentials that can **change accounts that spend real money**.
Treat them accordingly.

- **Never commit credentials.** The `.gitignore` blocks `*.json` (except the
  example config), `.env`, `google-ads.yaml`, and key files — but keep the
  developer token, OAuth secrets, and any service-account key outside the
  repository regardless.
- Grant the credentials the least access they need, and prefer a scratch or
  test manager account while evaluating.
- Every write tool is a **dry run by default** (`validate_only`), applying a
  change only when called with `confirm=True`. Keep it that way: review the
  dry-run result before confirming, especially anything that changes budgets,
  bids, or campaign status.
- If a token or secret is ever exposed, revoke it immediately (Google Cloud
  OAuth credentials / the Google Ads API Center developer token) and rotate.
