from __future__ import annotations

import http.client
import json
import threading
import uuid
from contextlib import contextmanager
import app_server
from app_server import AppHandler, CubeFlowHTTPServer


@contextmanager
def running_server():
    server = CubeFlowHTTPServer(("127.0.0.1", 0), AppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(port: int, method: str, path: str, *, session_id: str | None = None, body: dict | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    headers = {}
    if session_id:
        headers["X-CubeFlow-Session"] = session_id
    encoded = None
    if body is not None:
        encoded = json.dumps(body)
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=encoded, headers=headers)
    response = connection.getresponse()
    payload = json.loads(response.read().decode("utf-8"))
    connection.close()
    return response.status, response.headers, payload


def test_healthz_is_available_for_hosting_checks():
    with running_server() as port:
        status, _headers, payload = request(port, "GET", "/healthz")
    assert status == 200
    assert payload == {"ok": True, "service": "CubeFlow app server"}


def test_browser_sample_endpoint_validates_payload_and_echoes_session():
    session_id = str(uuid.uuid4())
    with running_server() as port:
        status, headers, payload = request(
            port,
            "POST",
            "/api/scanner/samples",
            session_id=session_id,
            body={"samples": [], "centerBgr": [0, 0, 0]},
        )
    assert status == 400
    assert "3x3" in payload["error"]
    assert headers["X-CubeFlow-Session"] == session_id


def test_static_path_traversal_is_rejected():
    with running_server() as port:
        status, _headers, payload = request(port, "GET", "/../../README.md")
    assert status == 404
    assert payload["error"] == "Not found"


def test_hosted_mode_disables_native_camera_and_preview_routes(monkeypatch):
    monkeypatch.setattr(app_server, "HOSTED_MODE", True)
    session_id = str(uuid.uuid4())
    with running_server() as port:
        preview_status, _headers, preview_payload = request(
            port,
            "GET",
            "/api/scanner/preview.jpg",
            session_id=session_id,
        )
        launch_status, _headers, launch_payload = request(
            port,
            "POST",
            "/api/actions/launch-scanner",
            session_id=session_id,
            body={},
        )
    assert preview_status == 404
    assert "rendered locally" in preview_payload["error"]
    assert launch_status == 400
    assert "Start Camera" in launch_payload["error"]
