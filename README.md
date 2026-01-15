# RKNN LCM Client Nodes for ComfyUI

This repository provides ComfyUI custom nodes that allow ComfyUI workflows to call an external LCM Stable Diffusion server running on Rockchip NPUs (RK3588 / RKNPU2) over HTTP.

These nodes are clients only.
They do not run inference locally inside ComfyUI.

---

## What is the LCM Server?

The LCM server is a standalone FastAPI service that runs:
- Stable Diffusion 1.5 – Latent Consistency Model (LCM)
- RKNN2-accelerated inference on Rockchip NPUs
- Optional server-side Super-Resolution (SR) as a post-process

The server lives here:

👉 [LCM Server Repository](https://github.com/Mario5Gray/Stable-Diffusion-1.5-LCM-ONNX-RKNN2)

### Key characteristics of the LCM server
- Runs on RK3588 / RK356x devices
- Uses RKNN2 (not CUDA, not CPU inference)
- Optimized for low-step LCM generation (2–8 steps typical)
- Supports:
  - `/generate` → text-to-image
  - `/superres` → image super-resolution
- Manages:
  - Worker isolation (one RKNN runtime per worker)
  - Request queuing / backpressure
  - Optional HAProxy / multi-node routing

This ComfyUI plugin simply calls that service.

---

## What This ComfyUI Plugin Does

This plugin adds HTTP client nodes to ComfyUI that:
- Send prompts or images to the LCM server
- Receive finished images back
- Convert results into ComfyUI IMAGE tensors
- Fit cleanly into standard ComfyUI workflows

### What it does not do
- ❌ No local Stable Diffusion inference
- ❌ No CUDA / GPU usage
- ❌ No model loading inside ComfyUI
- ❌ No sampler / latent manipulation

Think of these nodes as remote render nodes.

---

## Provided Nodes

### 1. RKNN LCM Generate (HTTP)

Calls the server's `/generate` endpoint.

#### Purpose
- Generate images using LCM-SD on an external Rockchip device.

#### Inputs
- API base URL(s) (single or multiple, round-robin)
- Prompt (multiline)
- Image size (e.g. 512x512)
- Steps
- CFG
- Seed (-1 = random)
- Super-Resolution magnitude slider:
  - 0 = off
  - 1–4 = number of SR passes (server may clamp)

#### Outputs
- IMAGE (ComfyUI tensor)
- Info string (backend, seed, SR status, timing)

---

### 2. RKNN SuperRes Upload (HTTP)

Calls the server's `/superres` endpoint.

#### Purpose
- Super-resolve an existing ComfyUI image using the server's RKNN SR model.

#### Inputs
- API base URL(s)
- IMAGE input
- SR magnitude:
  - 0 = bypass
  - 1–4 = number of SR passes
- Timeout

#### Outputs
- IMAGE (upscaled)
- Info string (passes, scale, backend)

---

## Backend Selection & Scaling

The nodes accept multiple API bases, for example:

