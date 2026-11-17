"""API Gateway: punto único de entrada. Verifica el token, enruta a cada microservicio
y orquesta el flujo «foto → texto → página de la biblioteca»."""
import os

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from common import registry
from common.security import bearer_token, decode_token

SERVICES = ["auth", "library", "notes", "ocr", "ai", "backup"]
PUBLIC = {("auth", "register"), ("auth", "login")}
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway – Tu biblioteca física en digital")
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    @app.get("/health")
    async def health():
        status = {}
        for name in SERVICES:
            try:
                async with registry.client(name, timeout=3) as c:
                    status[name] = "ok" if (await c.get("/health")).status_code == 200 else "error"
            except Exception:
                status[name] = "down"
        return {"status": "ok" if all(v == "ok" for v in status.values()) else "degraded", "services": status}

    @app.post("/api/scan", status_code=201)
    async def scan(request: Request, file: UploadFile = File(...), book_id: int = Form(...),
                   page_number: int | None = Form(default=None)):
        auth = request.headers.get("authorization")
        decode_token(bearer_token(auth))
        headers = registry.forward_headers(auth)
        raw = await file.read()
        try:
            async with registry.client("ocr", timeout=60) as c:
                ocr = await c.post("/extract", headers=headers,
                                   files={"file": (file.filename or "page.png", raw, file.content_type or "image/png")})
        except Exception:
            raise HTTPException(503, "El servicio OCR no responde")
        if ocr.status_code != 200:
            raise HTTPException(ocr.status_code, ocr.json().get("detail", "Error de OCR"))
        result = ocr.json()
        if not result["text"].strip():
            raise HTTPException(422, "No se detectó texto en la imagen. Prueba con mejor luz y enfoque.")
        payload = {"text": result["text"], "source": "ocr"}
        if page_number:
            payload["page_number"] = page_number
        try:
            async with registry.client("library") as c:
                page = await c.post(f"/books/{book_id}/pages", headers=headers, json=payload)
        except Exception:
            raise HTTPException(503, "El servicio de biblioteca no responde")
        if page.status_code != 201:
            raise HTTPException(page.status_code, page.json().get("detail", "No se pudo guardar la página"))
        return {"page": page.json(), "ocr": {"confidence": result["confidence"], "language": result["language"]}}

    @app.api_route("/api/{service}/{path:path}", methods=METHODS)
    async def proxy(service: str, path: str, request: Request):
        if service not in SERVICES:
            raise HTTPException(404, "Servicio desconocido")
        if (service, path) not in PUBLIC:
            decode_token(bearer_token(request.headers.get("authorization")))
        headers = {k: v for k, v in request.headers.items() if k.lower() in ("authorization", "content-type")}
        try:
            async with registry.client(service, timeout=60) as c:
                r = await c.request(request.method, "/" + path, params=dict(request.query_params),
                                    content=await request.body(), headers=headers)
        except Exception:
            raise HTTPException(503, f"El servicio {service} no está disponible")
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

    return app
