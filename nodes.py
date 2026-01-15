import io
import time
import random
import requests
import numpy as np
from PIL import Image

# ComfyUI uses torch tensors for IMAGE type (B,H,W,C) float 0..1
import torch


# ----------------------------
# Helpers
# ----------------------------
def _parse_bases(s: str):
    if not s:
        return []
    parts = []
    for chunk in str(s).split(";"):
        for sub in chunk.split(","):
            u = sub.strip()
            if u:
                parts.append(u.rstrip("/"))
    return parts


class _RRPicker:
    def __init__(self):
        self.i = 0

    def pick(self, bases):
        if not bases:
            return ""
        u = bases[self.i % len(bases)]
        self.i += 1
        return u


_rr = _RRPicker()


def _pil_to_comfy_tensor(pil: Image.Image):
    pil = pil.convert("RGB")
    arr = np.asarray(pil).astype(np.float32) / 255.0  # HWC
    t = torch.from_numpy(arr)[None, ...]              # 1HWC
    return t


def _comfy_tensor_to_png_bytes(img_tensor):
    """
    img_tensor: torch [B,H,W,C] float 0..1
    We'll use only the first image in batch.
    """
    if isinstance(img_tensor, torch.Tensor):
        t = img_tensor
    else:
        t = torch.tensor(img_tensor)

    t = t.detach().cpu()
    if t.ndim == 4:
        t = t[0]
    # HWC
    arr = (t.clamp(0, 1).numpy() * 255.0).astype(np.uint8)
    pil = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def _safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def _ensure_size_str(size_choice: str):
    # ComfyUI dropdown gives exact strings; just validate quickly
    s = str(size_choice).lower().strip()
    if "x" not in s:
        raise ValueError("size must be like 512x512")
    w, h = s.split("x", 1)
    int(w); int(h)
    return s


# ----------------------------
# Node: RKNN LCM Generate
# ----------------------------
class RKNN_LCM_Generate:
    """
    Calls POST /generate on your service.
    Returns IMAGE.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # allow multiple backends separated by ; or ,
                "api_bases": ("STRING", {"default": "http://node2:4200"}),
                "prompt": ("STRING", {"multiline": True, "default": "a cinematic photograph of a futuristic city at sunset"}),
                "size": (["256x256", "384x384", "512x512", "640x360", "640x384"], {"default": "512x512"}),
                "steps": ("INT", {"default": 4, "min": 1, "max": 50}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 20.0, "step": 0.1}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1}),  # -1 => random
                # SR magnitude slider per your latest: 0..4, 0=off
                "superres_magnitude": ("INT", {"default": 0, "min": 0, "max": 4}),
                "timeout_s": ("FLOAT", {"default": 120.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "info")
    FUNCTION = "run"
    CATEGORY = "rknn/lcm"

    def run(self, api_bases, prompt, size, steps, cfg, seed, superres_magnitude, timeout_s):
        bases = _parse_bases(api_bases)
        base = _rr.pick(bases) if bases else str(api_bases).rstrip("/")

        size = _ensure_size_str(size)

        if seed is None or int(seed) < 0:
            seed_val = random.randint(0, 99_999_999)
        else:
            seed_val = int(seed)

        # map magnitude: 0=off, 1..4 => /generate superres true and magnitude capped to backend (your backend is 1..3 today)
        # We'll send magnitude if >0; backend can clamp/reject.
        sr_on = int(superres_magnitude) > 0

        body = {
            "prompt": str(prompt),
            "size": size,
            "num_inference_steps": int(steps),
            "guidance_scale": float(cfg),
            "seed": int(seed_val),
            "superres": bool(sr_on),
            "superres_format": "png",
            "superres_quality": 92,
        }

        if sr_on:
            body["superres_magnitude"] = int(superres_magnitude)  # your server currently accepts 1..3; ok if you later extend to 4

        url = f"{base}/generate" if base else "/generate"

        t0 = time.time()
        r = requests.post(url, json=body, timeout=float(timeout_s))
        dt = time.time() - t0

        if r.status_code != 200:
            # Try to show the FastAPI detail if present
            detail = None
            try:
                detail = r.json().get("detail")
            except Exception:
                detail = r.text
            raise RuntimeError(f"/generate failed {r.status_code}: {detail}")

        img_bytes = r.content
        pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img = _pil_to_comfy_tensor(pil)

        seed_hdr = r.headers.get("X-Seed", str(seed_val))
        did_sr = r.headers.get("X-SuperRes", "0")
        sr_passes = r.headers.get("X-SR-Passes", "")
        backend = r.headers.get("X-LCM-Backend") or r.headers.get("X-Backend") or r.headers.get("X-Host") or ""

        info = f"backend={backend or base} seed={seed_hdr} sr={did_sr}"
        if sr_passes:
            info += f" passes={sr_passes}"
        info += f" time={dt:.2f}s"

        return (img, info)


# ----------------------------
# Node: RKNN SuperRes Upload
# ----------------------------
class RKNN_SuperRes_Upload:
    """
    Calls POST /superres with a ComfyUI IMAGE input.
    magnitude: 0..4 where 0=passthrough (no call).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_bases": ("STRING", {"default": "http://node2:4200"}),
                "image": ("IMAGE",),
                "magnitude": ("INT", {"default": 2, "min": 0, "max": 4}),
                "timeout_s": ("FLOAT", {"default": 120.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "info")
    FUNCTION = "run"
    CATEGORY = "rknn/superres"

    def run(self, api_bases, image, magnitude, timeout_s):
        mag = int(magnitude)
        if mag <= 0:
            return (image, "SR bypass (magnitude=0)")

        bases = _parse_bases(api_bases)
        base = _rr.pick(bases) if bases else str(api_bases).rstrip("/")
        url = f"{base}/superres" if base else "/superres"

        png_bytes = _comfy_tensor_to_png_bytes(image)

        files = {
            "file": ("input.png", png_bytes, "image/png"),
        }
        data = {
            "magnitude": str(mag),
            "out_format": "png",
            "quality": "92",
        }

        t0 = time.time()
        r = requests.post(url, files=files, data=data, timeout=float(timeout_s))
        dt = time.time() - t0

        if r.status_code != 200:
            detail = None
            try:
                detail = r.json().get("detail")
            except Exception:
                detail = r.text
            raise RuntimeError(f"/superres failed {r.status_code}: {detail}")

        out_bytes = r.content
        pil = Image.open(io.BytesIO(out_bytes)).convert("RGB")
        out = _pil_to_comfy_tensor(pil)

        passes = r.headers.get("X-SR-Passes") or r.headers.get("X-SR-Magnitude") or str(mag)
        scale = r.headers.get("X-SR-Scale-Per-Pass") or r.headers.get("X-SR-Scale") or ""
        backend = r.headers.get("X-LCM-Backend") or r.headers.get("X-Backend") or r.headers.get("X-Host") or ""

        info = f"backend={backend or base} passes={passes}"
        if scale:
            info += f" scale/pass={scale}"
        info += f" time={dt:.2f}s"

        return (out, info)


# ----------------------------
# ComfyUI registration
# ----------------------------
NODE_CLASS_MAPPINGS = {
    "RKNN LCM Generate": RKNN_LCM_Generate,
    "RKNN SuperRes Upload": RKNN_SuperRes_Upload,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RKNN LCM Generate": "RKNN LCM Generate (HTTP)",
    "RKNN SuperRes Upload": "RKNN SuperRes (HTTP Upload)",
}
