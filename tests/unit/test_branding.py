import apply_branding as b


def test_rebrand_text_rules():
    assert b.rebrand_text("UDS Launcher") == "LibreVDI Client"
    assert b.rebrand_text("UDS-Launcher herunterladen") == "LibreVDI-Client herunterladen"
    assert b.rebrand_text("UDS Actor for windows machines") == "LibreVDI Agent for windows machines"
    assert b.rebrand_text("UDS Akteur für Windows") == "LibreVDI Agent für Windows"
    assert b.rebrand_text("UDS Enterprise") == "LibreVDI"
    assert b.rebrand_text("Welcome to UDS") == "Welcome to LibreVDI"
    # attribution to the upstream project stays
    assert b.rebrand_text("OpenUDS github repository") == "OpenUDS github repository"
    assert b.rebrand_text("You can access UDS Open Source code at") == "You can access OpenUDS Open Source code at"
    # identifiers are not words
    assert b.rebrand_text("launchUDSUrl UDS_TOKEN") == "launchUDSUrl UDS_TOKEN"


def test_rebrand_bundle_exact_and_protected():
    js = (
        'a="UDS Launcher";b=["UDS","Security"];c="UDS ID";'
        'd=gettext("UDS transports for this client");e===\'"\';f="UDS Administration";'
        'href:"https://www.udsenterprise.com";this.title="UDS";'
    )
    out, count, leftovers = b.rebrand_bundle(js, {"UDS transports for this client", "UDS ID", "UDS Administration"})
    assert '"LibreVDI Client"' in out
    assert '"LibreVDI transports for this client"' in out
    assert '"LibreVDI Administration"' in out
    assert '["UDS","Security"]' in out  # functional config section name untouched
    assert '"UDS ID"' in out
    assert 'this.title="LibreVDI"' in out
    assert b.PROJECT_URL in out
    assert count == 3
    assert set(leftovers) == {"UDS", "UDS ID"}


def test_replace_loading_logo():
    css = ".x{a:b}.app-loading .logo{width:1px;background:url(data:image/png;base64,AAAA) no-repeat}"
    out = b.replace_loading_logo(css, "data:image/png;base64,BBBB")
    assert "AAAA" not in out and "BBBB" in out


def test_sri_format():
    assert b.sri(b"abc").startswith("sha384-")
