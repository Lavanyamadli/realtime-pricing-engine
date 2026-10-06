from app.ingestion.upstream import _auth_failed, _auth_succeeded


def test_recognizes_live_authentication_response() -> None:
    assert _auth_succeeded({"event": "authenticated", "success": True})


def test_reconnects_when_provider_reports_an_existing_session() -> None:
    assert _auth_failed({"event": "error", "message": "already have an active session"})
