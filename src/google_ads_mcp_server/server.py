#!/usr/bin/env python3
"""
google-ads-mcp-server — a Google Ads MCP server with read AND write access.

Reads run GAQL (Google Ads Query Language) queries plus convenience listers for
campaigns, ad groups, ads, budgets, and keywords. Writes cover campaign budgets,
campaigns, ad groups, bids, and keywords.

SAFETY: because Google Ads spends real money, EVERY write tool is a dry run by
default. It sends the change to the API with `validate_only=True`, which checks
the request without applying it, and returns the validation result. Nothing is
actually changed until you re-run the same tool with `confirm=True`. This is the
same idea as GA4's `validate=True` and GTM's `confirm=True` guards.

Authentication uses the standard google-ads client configuration, loaded from
environment variables (GoogleAdsClient.load_from_env) or, if
GOOGLE_ADS_CONFIGURATION_FILE_PATH is set, from a google-ads.yaml file. Either
way you need a **developer token** (with Basic access for real accounts) and
credentials — OAuth2 (client id/secret/refresh token) or a service account with
domain-wide delegation. See the README for setup.
"""

import os
from typing import Optional

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.api_core import protobuf_helpers
from google.protobuf.json_format import MessageToDict

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("google-ads")

# --- lazy client construction (so importing the module needs no credentials) --
_state: dict = {}


def ads_client() -> GoogleAdsClient:
    """Build (once) and return an authenticated GoogleAdsClient.

    Configuration is read from a google-ads.yaml file if
    GOOGLE_ADS_CONFIGURATION_FILE_PATH is set, otherwise from the standard
    GOOGLE_ADS_* environment variables.
    """
    if "client" not in _state:
        cfg_path = os.environ.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH")
        if cfg_path:
            _state["client"] = GoogleAdsClient.load_from_storage(cfg_path)
        else:
            # Requires GOOGLE_ADS_DEVELOPER_TOKEN plus either OAuth
            # (GOOGLE_ADS_CLIENT_ID / _CLIENT_SECRET / _REFRESH_TOKEN) or a
            # service account, and usually GOOGLE_ADS_LOGIN_CUSTOMER_ID.
            _state["client"] = GoogleAdsClient.load_from_env()
    return _state["client"]


def _cid(customer_id: str) -> str:
    """Normalize a customer id to digits only (strip dashes/spaces)."""
    return str(customer_id).replace("-", "").replace(" ", "").strip()


def _rows(customer_id: str, query: str) -> list[dict]:
    """Run a GAQL query and return rows as plain dicts."""
    client = ads_client()
    ga = client.get_service("GoogleAdsService")
    out = []
    for row in ga.search(customer_id=_cid(customer_id), query=query):
        out.append(MessageToDict(row._pb, preserving_proto_field_name=True))
    return out


def _run(fn):
    """Execute an API call and normalize Google Ads errors to a dict."""
    try:
        return fn()
    except GoogleAdsException as ex:
        errors = []
        for err in ex.failure.errors:
            errors.append(
                {
                    "message": err.message,
                    "error_code": str(err.error_code).strip(),
                    "location": [
                        fpe.field_name for fpe in err.location.field_path_elements
                    ]
                    if err.location
                    else [],
                }
            )
        return {"error": True, "request_id": ex.request_id, "errors": errors}
    except Exception as e:  # noqa: BLE001
        return {"error": True, "detail": str(e)}


def _mutate_result(resp, confirm: bool) -> dict:
    """Shape a mutate response. Dry runs report validation only."""
    if not confirm:
        return {
            "applied": False,
            "validated": True,
            "note": "Dry run OK — the change is valid but was NOT applied. "
            "Re-run with confirm=true to apply it.",
        }
    results = [getattr(r, "resource_name", None) for r in getattr(resp, "results", [])]
    return {"applied": True, "results": results}


# ===========================================================================
# Diagnostics
# ===========================================================================


@mcp.tool()
def ads_whoami() -> dict:
    """Show how this server is configured (login customer id, developer-token
    presence — masked) and list the Google Ads accounts it can access. Use this
    first to verify credentials and access."""
    info = {}
    dev = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    info["developer_token_set"] = bool(dev)
    if dev:
        info["developer_token_hint"] = dev[:4] + "…" + dev[-2:] if len(dev) > 6 else "set"
    info["login_customer_id"] = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    info["config_file"] = os.environ.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH")

    def _list():
        client = ads_client()
        svc = client.get_service("CustomerService")
        res = svc.list_accessible_customers()
        return {"resource_names": list(res.resource_names)}

    res = _run(_list)
    if isinstance(res, dict) and res.get("error"):
        info["access_error"] = res
    else:
        info["accessible_customers"] = res["resource_names"]
    return info


# ===========================================================================
# Reads
# ===========================================================================


@mcp.tool()
def list_accessible_customers() -> dict:
    """List the resource names of the Google Ads customers this login can access.
    Each looks like 'customers/1234567890'; the digits are the customer id."""
    def _list():
        client = ads_client()
        svc = client.get_service("CustomerService")
        res = svc.list_accessible_customers()
        return {"resource_names": list(res.resource_names)}

    return _run(_list)


@mcp.tool()
def search(customer_id: str, query: str) -> dict:
    """Run a GAQL (Google Ads Query Language) query and return the rows. This is
    the general-purpose read tool — anything reportable in Google Ads can be
    fetched here. Example query:
    "SELECT campaign.id, campaign.name, campaign.status,
     metrics.impressions, metrics.clicks, metrics.cost_micros
     FROM campaign WHERE segments.date DURING LAST_30_DAYS
     ORDER BY metrics.cost_micros DESC"."""
    return _run(lambda: {"rows": _rows(customer_id, query)})


@mcp.tool()
def list_campaigns(customer_id: str, include_removed: bool = False) -> dict:
    """List campaigns with id, name, status, channel type, and budget id."""
    where = "" if include_removed else "WHERE campaign.status != 'REMOVED'"
    q = (
        "SELECT campaign.id, campaign.name, campaign.status, "
        "campaign.advertising_channel_type, campaign_budget.id, "
        "campaign_budget.amount_micros FROM campaign "
        f"{where} ORDER BY campaign.id"
    )
    return _run(lambda: {"rows": _rows(customer_id, q)})


@mcp.tool()
def list_ad_groups(customer_id: str, campaign_id: Optional[str] = None) -> dict:
    """List ad groups (optionally filtered to one campaign) with id, name,
    status, type, and CPC bid."""
    where = "WHERE ad_group.status != 'REMOVED'"
    if campaign_id:
        where += f" AND campaign.id = {int(campaign_id)}"
    q = (
        "SELECT ad_group.id, ad_group.name, ad_group.status, ad_group.type, "
        "ad_group.cpc_bid_micros, campaign.id FROM ad_group "
        f"{where} ORDER BY ad_group.id"
    )
    return _run(lambda: {"rows": _rows(customer_id, q)})


@mcp.tool()
def list_ads(customer_id: str, ad_group_id: Optional[str] = None) -> dict:
    """List ads (optionally filtered to one ad group) with id, type, and status."""
    where = "WHERE ad_group_ad.status != 'REMOVED'"
    if ad_group_id:
        where += f" AND ad_group.id = {int(ad_group_id)}"
    q = (
        "SELECT ad_group_ad.ad.id, ad_group_ad.ad.type, ad_group_ad.status, "
        "ad_group_ad.ad.name, ad_group.id FROM ad_group_ad "
        f"{where} ORDER BY ad_group_ad.ad.id"
    )
    return _run(lambda: {"rows": _rows(customer_id, q)})


@mcp.tool()
def list_campaign_budgets(customer_id: str) -> dict:
    """List campaign budgets with id, name, amount (micros), and delivery method."""
    q = (
        "SELECT campaign_budget.id, campaign_budget.name, "
        "campaign_budget.amount_micros, campaign_budget.delivery_method, "
        "campaign_budget.status FROM campaign_budget "
        "WHERE campaign_budget.status != 'REMOVED' ORDER BY campaign_budget.id"
    )
    return _run(lambda: {"rows": _rows(customer_id, q)})


@mcp.tool()
def list_keywords(customer_id: str, ad_group_id: Optional[str] = None) -> dict:
    """List keyword criteria (optionally filtered to one ad group) with text,
    match type, status, and the criterion id."""
    where = "WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.status != 'REMOVED'"
    if ad_group_id:
        where += f" AND ad_group.id = {int(ad_group_id)}"
    q = (
        "SELECT ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
        "ad_group_criterion.keyword.match_type, ad_group_criterion.status, "
        "ad_group.id FROM ad_group_criterion "
        f"{where} ORDER BY ad_group_criterion.criterion_id"
    )
    return _run(lambda: {"rows": _rows(customer_id, q)})


@mcp.tool()
def campaign_performance(
    customer_id: str, start_date: str, end_date: str, limit: int = 50
) -> dict:
    """Report per-campaign performance (impressions, clicks, cost, conversions)
    between two dates (YYYY-MM-DD), highest spend first."""
    q = (
        "SELECT campaign.id, campaign.name, metrics.impressions, metrics.clicks, "
        "metrics.cost_micros, metrics.conversions, metrics.conversions_value "
        "FROM campaign "
        f"WHERE segments.date BETWEEN '{start_date}' AND '{end_date}' "
        f"ORDER BY metrics.cost_micros DESC LIMIT {int(limit)}"
    )
    return _run(lambda: {"rows": _rows(customer_id, q)})


# ===========================================================================
# Writes — every one is a dry run unless confirm=True
# ===========================================================================


@mcp.tool()
def create_campaign_budget(
    customer_id: str,
    name: str,
    amount_micros: int,
    delivery_method: str = "STANDARD",
    confirm: bool = False,
) -> dict:
    """Create a campaign budget. amount_micros is the daily amount in micros
    (1_000_000 micros = 1 unit of the account currency, e.g. $5/day = 5000000).
    delivery_method is 'STANDARD' or 'ACCELERATED'. Dry run unless confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("CampaignBudgetService")
        op = client.get_type("CampaignBudgetOperation")
        b = op.create
        b.name = name
        b.amount_micros = int(amount_micros)
        b.delivery_method = client.enums.BudgetDeliveryMethodEnum[delivery_method.upper()]
        resp = svc.mutate_campaign_budgets(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


@mcp.tool()
def update_campaign_budget(
    customer_id: str, budget_id: str, amount_micros: int, confirm: bool = False
) -> dict:
    """Change a campaign budget's daily amount (in micros). Dry run unless
    confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("CampaignBudgetService")
        op = client.get_type("CampaignBudgetOperation")
        b = op.update
        b.resource_name = svc.campaign_budget_path(_cid(customer_id), budget_id)
        b.amount_micros = int(amount_micros)
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, b._pb))
        resp = svc.mutate_campaign_budgets(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


@mcp.tool()
def create_campaign(
    customer_id: str,
    name: str,
    budget_id: str,
    advertising_channel_type: str = "SEARCH",
    status: str = "PAUSED",
    confirm: bool = False,
) -> dict:
    """Create a campaign attached to an existing budget. Defaults to a PAUSED
    Search campaign with Manual CPC bidding and Google Search + search partners
    enabled (content network off). Created PAUSED by default so it never starts
    spending unexpectedly — enable it later with update_campaign_status. Dry run
    unless confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("CampaignService")
        budget_svc = client.get_service("CampaignBudgetService")
        op = client.get_type("CampaignOperation")
        c = op.create
        c.name = name
        c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum[
            advertising_channel_type.upper()
        ]
        c.status = client.enums.CampaignStatusEnum[status.upper()]
        c.campaign_budget = budget_svc.campaign_budget_path(_cid(customer_id), budget_id)
        # Select Manual CPC bidding by touching the field.
        c.manual_cpc.enhanced_cpc_enabled = False
        c.network_settings.target_google_search = True
        c.network_settings.target_search_network = True
        c.network_settings.target_content_network = False
        resp = svc.mutate_campaigns(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


@mcp.tool()
def update_campaign_status(
    customer_id: str, campaign_id: str, status: str, confirm: bool = False
) -> dict:
    """Set a campaign's status: 'ENABLED' (start/resume serving), 'PAUSED'
    (stop serving), or 'REMOVED' (delete). Dry run unless confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("CampaignService")
        op = client.get_type("CampaignOperation")
        c = op.update
        c.resource_name = svc.campaign_path(_cid(customer_id), campaign_id)
        c.status = client.enums.CampaignStatusEnum[status.upper()]
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, c._pb))
        resp = svc.mutate_campaigns(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


@mcp.tool()
def create_ad_group(
    customer_id: str,
    campaign_id: str,
    name: str,
    cpc_bid_micros: Optional[int] = None,
    status: str = "ENABLED",
    confirm: bool = False,
) -> dict:
    """Create a standard Search ad group under a campaign. cpc_bid_micros is an
    optional default max CPC bid in micros. Dry run unless confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("AdGroupService")
        camp_svc = client.get_service("CampaignService")
        op = client.get_type("AdGroupOperation")
        ag = op.create
        ag.name = name
        ag.campaign = camp_svc.campaign_path(_cid(customer_id), campaign_id)
        ag.status = client.enums.AdGroupStatusEnum[status.upper()]
        ag.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
        if cpc_bid_micros is not None:
            ag.cpc_bid_micros = int(cpc_bid_micros)
        resp = svc.mutate_ad_groups(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


@mcp.tool()
def update_ad_group_status(
    customer_id: str, ad_group_id: str, status: str, confirm: bool = False
) -> dict:
    """Set an ad group's status: 'ENABLED', 'PAUSED', or 'REMOVED'. Dry run
    unless confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("AdGroupService")
        op = client.get_type("AdGroupOperation")
        ag = op.update
        ag.resource_name = svc.ad_group_path(_cid(customer_id), ad_group_id)
        ag.status = client.enums.AdGroupStatusEnum[status.upper()]
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, ag._pb))
        resp = svc.mutate_ad_groups(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


@mcp.tool()
def update_ad_group_bid(
    customer_id: str, ad_group_id: str, cpc_bid_micros: int, confirm: bool = False
) -> dict:
    """Change an ad group's default max CPC bid (in micros). Dry run unless
    confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("AdGroupService")
        op = client.get_type("AdGroupOperation")
        ag = op.update
        ag.resource_name = svc.ad_group_path(_cid(customer_id), ad_group_id)
        ag.cpc_bid_micros = int(cpc_bid_micros)
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, ag._pb))
        resp = svc.mutate_ad_groups(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


@mcp.tool()
def add_keyword(
    customer_id: str,
    ad_group_id: str,
    text: str,
    match_type: str = "BROAD",
    confirm: bool = False,
) -> dict:
    """Add a keyword to an ad group. match_type is 'EXACT', 'PHRASE', or
    'BROAD'. Dry run unless confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("AdGroupCriterionService")
        ag_svc = client.get_service("AdGroupService")
        op = client.get_type("AdGroupCriterionOperation")
        crit = op.create
        crit.ad_group = ag_svc.ad_group_path(_cid(customer_id), ad_group_id)
        crit.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        crit.keyword.text = text
        crit.keyword.match_type = client.enums.KeywordMatchTypeEnum[match_type.upper()]
        resp = svc.mutate_ad_group_criteria(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


@mcp.tool()
def update_keyword_status(
    customer_id: str,
    ad_group_id: str,
    criterion_id: str,
    status: str,
    confirm: bool = False,
) -> dict:
    """Set a keyword's status: 'ENABLED', 'PAUSED', or 'REMOVED'. criterion_id
    is the keyword's criterion id (from list_keywords). Dry run unless
    confirm=True."""
    def _do():
        client = ads_client()
        svc = client.get_service("AdGroupCriterionService")
        op = client.get_type("AdGroupCriterionOperation")
        crit = op.update
        crit.resource_name = svc.ad_group_criterion_path(
            _cid(customer_id), ad_group_id, criterion_id
        )
        crit.status = client.enums.AdGroupCriterionStatusEnum[status.upper()]
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, crit._pb))
        resp = svc.mutate_ad_group_criteria(
            request={"customer_id": _cid(customer_id), "operations": [op], "validate_only": not confirm}
        )
        return _mutate_result(resp, confirm)

    return _run(_do)


def main() -> None:
    """Console-script entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
