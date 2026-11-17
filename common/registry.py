"""Registro de servicios: cómo un servicio encuentra a otro.

En producción usa HTTP real (variables *_URL). En pruebas se conectan las apps
directamente en memoria con `use_apps`, sin abrir puertos.
"""
import os

import httpx

DEFAULT_PORTS = {"auth": 8001, "library": 8002, "notes": 8003, "ocr": 8004, "ai": 8005, "backup": 8006}
_transports: dict[str, httpx.ASGITransport] = {}


def service_url(name: str) -> str:
    return os.getenv(f"{name.upper()}_URL", f"http://127.0.0.1:{DEFAULT_PORTS[name]}")


def use_apps(apps: dict) -> None:
    _transports.clear()
    for name, app in apps.items():
        _transports[name] = httpx.ASGITransport(app=app)


def client(name: str, timeout: float = 20.0) -> httpx.AsyncClient:
    transport = _transports.get(name)
    base = f"http://{name}.test" if transport else service_url(name)
    return httpx.AsyncClient(base_url=base, transport=transport, timeout=timeout)


def forward_headers(authorization: str | None) -> dict:
    return {"Authorization": authorization} if authorization else {}
