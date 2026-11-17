"""Servicio OCR: convierte la foto de una página en texto (Tesseract)."""
import io
from typing import Callable

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from common.security import current_user_id

MAX_BYTES = 10 * 1024 * 1024
ALLOWED = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp", "image/tiff"}


class OcrUnavailable(Exception):
    pass


def tesseract_engine(image: Image.Image) -> dict:
    """Motor real. Usa español + inglés si el idioma español está instalado."""
    try:
        import pytesseract

        langs = pytesseract.get_languages(config="")
        lang = "spa+eng" if "spa" in langs else "eng"
        data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(image, lang=lang)
    except Exception as exc:  # binario no instalado o fallo del motor
        raise OcrUnavailable(str(exc))
    confs = [float(c) for c, w in zip(data["conf"], data["text"]) if str(c) not in ("-1", "") and w.strip()]
    return {"text": text.strip(), "confidence": round(sum(confs) / len(confs), 1) if confs else 0.0, "language": lang}


def preprocess(image: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(image).convert("L")
    img = ImageOps.autocontrast(img)
    if max(img.size) < 1200:  # las fotos pequeñas se reconocen mejor ampliadas
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    return img


def create_app(engine: Callable[[Image.Image], dict] | None = None) -> FastAPI:
    run = engine or tesseract_engine
    app = FastAPI(title="Servicio OCR")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "ocr"}

    @app.post("/extract")
    async def extract(file: UploadFile = File(...), uid: int = Depends(current_user_id)):
        if (file.content_type or "").lower() not in ALLOWED:
            raise HTTPException(415, "El archivo debe ser una imagen (PNG, JPG, WEBP, BMP o TIFF)")
        raw = await file.read()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "La imagen supera los 10 MB")
        if not raw:
            raise HTTPException(400, "La imagen está vacía")
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(400, "No se pudo leer la imagen")
        try:
            result = run(preprocess(image))
        except OcrUnavailable:
            raise HTTPException(503, "El motor OCR no está disponible")
        return {**result, "engine": "tesseract", "width": image.width, "height": image.height}

    return app
