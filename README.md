# Back-biblioteca · «Tu biblioteca física en digital»

Backend de la app que convierte la foto de una página de un libro impreso en texto editable (OCR),
permite subrayar, tomar notas, organizar una biblioteca digital y guardar respaldos.

## Arquitectura (microservicios con FastAPI)

```
                  ┌──────────────┐
  UI ───────────▶ │   gateway    │  :8000  valida el JWT, enruta y orquesta «foto → página»
                  └──────┬───────┘
     ┌──────┬────────┬───┴────┬────────┬─────────┐
     ▼      ▼        ▼        ▼        ▼         ▼
   auth   library   notes    ocr       ai      backup
   :8001  :8002     :8003    :8004     :8005   :8006
```

| Servicio | Responsabilidad | Base de datos |
|---|---|---|
| `gateway` | Único punto expuesto. Verifica el token, enruta `/api/<servicio>/...`, CORS y el flujo `POST /api/scan` | – |
| `auth` | Registro, inicio de sesión (JWT), perfil | `auth.db` |
| `library` | Libros, páginas con texto editable, búsqueda, exportación | `library.db` |
| `notes` | Subrayados con color y notas; valida cada página consultando a `library` | `notes.db` |
| `ocr` | Imagen → texto con Tesseract (español + inglés si está instalado) | – |
| `ai` | Resumen extractivo, mapa de conceptos y fragmentos para lectura en voz alta | – |
| `backup` | Instantáneas de la biblioteca + restauración (habla con `library` y `notes`) | `backup.db` |

Cada servicio tiene su propia base SQLite y valida el token por su cuenta; los datos de cada usuario están aislados.

## Requisitos
- Python 3.11+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (`sudo apt install tesseract-ocr tesseract-ocr-spa` en Debian/Ubuntu)

## Cómo correrlo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_all.py            # gateway en http://127.0.0.1:8000  (docs en /docs de cada servicio)
```

Con Docker: `docker compose up --build` (el gateway queda en el puerto 8000).

Variables útiles: `JWT_SECRET` (**cámbiala en producción**), `DATA_DIR`, `CORS_ORIGINS` (por defecto `*`).

## Pruebas

```bash
pytest -q
```

Las pruebas conectan los servicios entre sí en memoria (sin puertos) y cubren autenticación, aislamiento entre usuarios,
CRUD de la biblioteca, subrayados, OCR real, IA, respaldo/restauración y el flujo completo de escaneo por el gateway.

## Endpoints principales (todos bajo el gateway, con `Authorization: Bearer <token>` salvo registro y login)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/auth/register`, `/api/auth/login` | Crear cuenta / iniciar sesión |
| GET/POST | `/api/library/books` | Listar / crear libros |
| GET/POST | `/api/library/books/{id}/pages` | Páginas de un libro |
| PUT | `/api/library/pages/{id}` | Editar el texto reconocido |
| GET | `/api/library/search?q=` | Buscar en todas tus páginas |
| POST | `/api/scan` | Foto → OCR → nueva página (`multipart`: `file`, `book_id`, `page_number`) |
| POST | `/api/notes/pages/{id}/highlights` | Subrayar (`start`, `end`, `color`, `note`) |
| POST | `/api/ai/summary`, `/api/ai/concepts`, `/api/ai/read-aloud` | Resumen, mapa de conceptos, voz |
| POST | `/api/backup/snapshots` | Crear respaldo; `…/{id}/restore` lo restaura |

## Notas
- Proyecto académico (Uniempresarial, clase de Innovación). Las funciones de IA son ligeras y locales; se pueden cambiar por un modelo externo sin tocar el resto.
- Digitalizar libros protegidos tiene implicaciones de derecho de autor: el uso previsto es personal. Revisar con un abogado antes de lanzar.

## Despliegue en producción
El backend es un contenedor Docker (`python run_all.py`): el gateway escucha en `$PORT` y los 6 microservicios en puertos internos.
- **Render:** «New → Blueprint» sobre este repo (usa `render.yaml`, genera `JWT_SECRET` y monta un disco en `/data`).
- Variables: `JWT_SECRET` (obligatoria), `DATA_DIR`, `CORS_ORIGINS` (pon la URL de Vercel del UI).
- Verifica con `GET /health`.

### Modo demo en Vercel
`api/index.py` junta los 7 servicios en un solo proceso (conectados en memoria con `registry.use_apps`). Solo para demo: los datos viven en `/tmp` y se pierden al reiniciar la función, y sin Tesseract el escaneo responde 503. Para producción real usa el Dockerfile.
