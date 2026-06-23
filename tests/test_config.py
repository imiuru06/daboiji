import pytest

from dabwayo.config import (
    DEFAULT_PROVIDER,
    DEFAULT_TIMEOUT,
    Config,
    ConfigError,
    load_config,
)


def test_load_config_minimal():
    cfg = load_config({"DABWAYO_VIDEOGEN_URL": "https://example.com/"})
    assert cfg.base_url == "https://example.com/"
    assert cfg.provider == DEFAULT_PROVIDER
    assert cfg.api_key is None
    assert cfg.timeout == DEFAULT_TIMEOUT


def test_load_config_full():
    cfg = load_config(
        {
            "DABWAYO_VIDEOGEN_URL": "https://example.com",
            "DABWAYO_VIDEOGEN_PROVIDER": "Remote",
            "DABWAYO_VIDEOGEN_API_KEY": "secret",
            "DABWAYO_VIDEOGEN_TIMEOUT": "12.5",
        }
    )
    assert cfg.provider == "remote"  # normalised to lowercase
    assert cfg.api_key == "secret"
    assert cfg.timeout == 12.5


def test_missing_url_raises():
    with pytest.raises(ConfigError):
        load_config({})


def test_bad_timeout_raises():
    with pytest.raises(ConfigError):
        load_config({"DABWAYO_VIDEOGEN_URL": "https://x", "DABWAYO_VIDEOGEN_TIMEOUT": "nope"})


def test_nonpositive_timeout_raises():
    with pytest.raises(ConfigError):
        load_config({"DABWAYO_VIDEOGEN_URL": "https://x", "DABWAYO_VIDEOGEN_TIMEOUT": "0"})


def test_url_join():
    cfg = Config(base_url="https://example.com/")
    assert cfg.url("/generate") == "https://example.com/generate"
    assert cfg.url("generate") == "https://example.com/generate"
