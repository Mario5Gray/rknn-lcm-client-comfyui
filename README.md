RKNN LCM Client Nodes for ComfyUI

This repository provides ComfyUI custom nodes that allow ComfyUI workflows to call an external LCM Stable Diffusion server running on Rockchip NPUs (RK3588 / RKNPU2) over HTTP.

These nodes are clients only.
They do not run inference locally inside ComfyUI.

⸻

What is the LCM Server?

The LCM server is a standalone FastAPI service that runs:
	•	Stable Diffusion 1.5 – Latent Consistency Model (LCM)
	•	RKNN2-accelerated inference on Rockchip NPUs
	•	Optional server-side Super-Resolution (SR) as a post-process

The server lives here:

👉 LCM Server Repository
https://github.com/Mario5Gray/Stable-Diffusion-1.5-LCM-ONNX-RKNN2

Key characteristics of the LCM server
	•	Runs on RK3588 / RK356x devices
	•	Uses RKNN2 (not CUDA, not CPU inference)
	•	Optimized for low-step LCM generation (2–8 steps typical)
	•	Supports:
	•	/generate → text-to-image
	•	/superres → image super-resolution
	•	Manages:
	•	Worker isolation (one RKNN runtime per worker)
	•	Request queuing / backpressure
	•	Optional HAProxy / multi-node routing

This ComfyUI plugin simply calls that service.

⸻

What This ComfyUI Plugin Does

This plugin adds HTTP client nodes to ComfyUI that:
	•	Send prompts or images to the LCM server
	•	Receive finished images back
	•	Convert results into ComfyUI IMAGE tensors
	•	Fit cleanly into standard ComfyUI workflows

What it does not do
	•	❌ No local Stable Diffusion inference
	•	❌ No CUDA / GPU usage
	•	❌ No model loading inside ComfyUI
	•	❌ No sampler / latent manipulation

Think of these nodes as remote render nodes.

⸻

Provided Nodes

1. RKNN LCM Generate (HTTP)

Calls the server’s /generate endpoint.

Purpose
	•	Generate images using LCM-SD on an external Rockchip device.

Inputs
	•	API base URL(s) (single or multiple, round-robin)
	•	Prompt (multiline)
	•	Image size (e.g. 512x512)
	•	Steps
	•	CFG
	•	Seed (-1 = random)
	•	Super-Resolution magnitude slider:
	•	0 = off
	•	1–4 = number of SR passes (server may clamp)

Outputs
	•	IMAGE (ComfyUI tensor)
	•	Info string (backend, seed, SR status, timing)

⸻

2. RKNN SuperRes Upload (HTTP)

Calls the server’s /superres endpoint.

Purpose
	•	Super-resolve an existing ComfyUI image using the server’s RKNN SR model.

Inputs
	•	API base URL(s)
	•	IMAGE input
	•	SR magnitude:
	•	0 = bypass
	•	1–4 = number of SR passes
	•	Timeout

Outputs
	•	IMAGE (upscaled)
	•	Info string (passes, scale, backend)

⸻

Backend Selection & Scaling

The nodes accept multiple API bases, for example:

http://node1:4200;http://node2:4200;http://node3:4200

Requests are sent in round-robin order, which pairs naturally with:
	•	HAProxy
	•	Multiple RK3588 boards
	•	Worker-isolated NPU inference

⸻

Expected Performance & Behavior

What to expect when using these nodes:
	•	✅ Very fast low-step generation (LCM-style)
	•	✅ Deterministic results when seed is fixed
	•	✅ No VRAM pressure on the ComfyUI machine
	•	✅ Suitable for headless or embedded inference boxes
	•	⚠️ VAE decode is slower than U-Net (known RKNN behavior)
	•	⚠️ SR is tile-based and memory-bounded by the server

All performance characteristics are dictated by the LCM server, not ComfyUI.

⸻

Typical Use Cases
	•	Offload image generation to RK3588 edge devices
	•	Centralize inference while keeping ComfyUI as the UI / workflow engine
	•	Mix LCM renders into larger ComfyUI pipelines
	•	Run server-side super-resolution without GPU usage

⸻

Summary

This plugin turns ComfyUI into a first-class client for a Rockchip-based LCM inference service.
	•	ComfyUI = workflow & orchestration
	•	LCM Server = inference & acceleration

Clean separation. No hacks. No unsafe RKNN sharing.

If you can call the server with curl, you can call it from ComfyUI.

⸻

If you want, next we can:
	•	Add ComfyUI previews with progress polling
	•	Add an A1111-compatible node
	•	Add OpenWebUI tool definitions
	•	Add ComfyUI workflow JSON examples

Just tell me where you want this to go next.