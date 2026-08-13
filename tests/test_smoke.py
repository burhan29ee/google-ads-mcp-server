"""Smoke tests: the package imports and pure helpers work without credentials."""


def test_package_version():
    import google_ads_mcp_server

    assert google_ads_mcp_server.__version__


def test_server_and_entrypoint():
    from google_ads_mcp_server import server

    assert callable(server.main)
    assert server.mcp is not None


def test_normalize_customer_id():
    from google_ads_mcp_server import server

    assert server._cid("123-456-7890") == "1234567890"
    assert server._cid(" 123 456 ") == "123456"
    assert server._cid("customers/999") == "customers/999".replace("-", "")


def test_dry_run_result_shape():
    from google_ads_mcp_server import server

    dry = server._mutate_result(None, confirm=False)
    assert dry["applied"] is False and dry["validated"] is True
