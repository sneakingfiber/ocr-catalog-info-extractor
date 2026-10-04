"""Client for glm-ocr served by Ollama."""

import base64
import io

import requests
from PIL import Image

PROMPTS = ("Table Recognition:", "Text Recognition:", "Figure Recognition:")


class OllamaOCR:
    def __init__(
        self,
        url: str = "http://localhost:11434",
        model: str = "glm-ocr:q8_0",
        prompt: str = "Table Recognition:",
        max_px: int = 1280,
        timeout: int = 300,
    ):
        self.url = url.rstrip("/")
        self.model = model
        self.prompt = prompt
        self.max_px = max_px
        self.timeout = timeout

    def _encode(self, img: Image.Image) -> str:
        w, h = img.size
        if max(w, h) > self.max_px:
            scale = self.max_px / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def recognize(self, img: Image.Image) -> str:
        """Run OCR on one page image and return the raw text."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": self.prompt, "images": [self._encode(img)]}],
            "stream": False,
            "keep_alive": 0,
        }
        resp = requests.post(f"{self.url}/api/chat", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
