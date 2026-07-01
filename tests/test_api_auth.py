import pytest
from fastapi import HTTPException

from app.main import verify_report_api_token


def test_report_api_token_allows_dev_mode_without_config(monkeypatch) -> None:
    monkeypatch.delenv("GATEWAY_API_TOKEN", raising=False)

    verify_report_api_token()


def test_report_api_token_accepts_bearer(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_API_TOKEN", "secret")

    verify_report_api_token(authorization="Bearer secret")


def test_report_api_token_accepts_x_api_key(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_API_TOKEN", "secret")

    verify_report_api_token(x_api_key="secret")


def test_report_api_token_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_API_TOKEN", "secret")

    with pytest.raises(HTTPException) as exc_info:
        verify_report_api_token()

    assert exc_info.value.status_code == 401
