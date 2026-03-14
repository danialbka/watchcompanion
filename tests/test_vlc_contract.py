from pathlib import Path


def test_vlc_readme_mentions_localhost_contract():
    text = Path("vlc/README.md").read_text()
    assert "127.0.0.1:42142" in text
    assert "GET_STATE" in text
    assert "timestamp" in text


def test_vlc_lua_extension_exposes_contract_fields():
    text = Path("vlc/companion_bridge.lua").read_text()
    for needle in [
        '"title"',
        '"uri"',
        '"timestamp"',
        '"length"',
        '"position"',
        '"state"',
    ]:
        assert needle in text
    assert "socket.bind(host, port)" in text
