import pytest

from chatglm_adapter.chatglm.cookies import (
    CookieStore,
    parse_cookie_header,
    serialize_cookie_header,
)
from chatglm_adapter.core.errors import ConfigurationError
from chatglm_adapter.security.secrets import atomic_write_secret, read_secret_file


def test_parse_cookie_header_handles_spacing_and_equals_in_values():
    header = "a=1;b=2; ssxmod_itna=1-x=y=z; empty=; chatglm_refresh_token=rt-1 "
    cookies = parse_cookie_header(header)
    assert cookies == {
        "a": "1",
        "b": "2",
        "ssxmod_itna": "1-x=y=z",
        "empty": "",
        "chatglm_refresh_token": "rt-1",
    }


def test_serialize_cookie_header_round_trip():
    cookies = {"a": "1", "chatglm_refresh_token": "rt-1", "waf": "x=y"}
    assert parse_cookie_header(serialize_cookie_header(cookies)) == cookies


def test_cookie_store_load_requires_refresh_token(tmp_path):
    cookie_file = tmp_path / "cookies"
    atomic_write_secret(cookie_file, "a=1; b=2")
    with pytest.raises(ConfigurationError):
        CookieStore.load(cookie_file)


def test_cookie_store_header_substitutes_access_token_only_when_present(tmp_path):
    cookie_file = tmp_path / "cookies"
    atomic_write_secret(cookie_file, "chatglm_refresh_token=rt-1; chatglm_token=old-access; waf=w")
    store = CookieStore.load(cookie_file)
    assert store.refresh_token == "rt-1"
    assert store.header() == "chatglm_refresh_token=rt-1; chatglm_token=old-access; waf=w"
    assert store.header(access_token="new-access") == (
        "chatglm_refresh_token=rt-1; chatglm_token=new-access; waf=w"
    )


def test_cookie_store_header_without_access_token_cookie_stays_untouched(tmp_path):
    cookie_file = tmp_path / "cookies"
    atomic_write_secret(cookie_file, "chatglm_refresh_token=rt-1")
    store = CookieStore.load(cookie_file)
    assert store.header(access_token="new-access") == "chatglm_refresh_token=rt-1"


def test_cookie_store_rotation_updates_memory_and_file(tmp_path):
    cookie_file = tmp_path / "cookies"
    atomic_write_secret(cookie_file, "waf=w; chatglm_refresh_token=rt-1")
    store = CookieStore.load(cookie_file)
    store.rotate_refresh_token("rt-2")
    assert store.refresh_token == "rt-2"
    assert read_secret_file(cookie_file) == "waf=w; chatglm_refresh_token=rt-2"
