#!/usr/bin/env python3
"""
Persistent Daemon Worker for Local FASHN VTON v1.5 Inference.
Maintains model weights in memory on Apple Silicon (MPS) or CUDA,
eliminating the ~5-second cold-start initialization per job.
Provides streaming progress reporting over a local UNIX domain socket.
"""

import sys
import os
import time
import json
import socket
import select
import threading
from pathlib import Path
from PIL import Image

# Ensure fashn-vton-1.5/src is in sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_src = os.path.abspath(os.path.join(script_dir, "../fashn-vton-1.5/src"))
if os.path.exists(repo_src) and repo_src not in sys.path:
    sys.path.insert(0, repo_src)

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib_apex_vto")
os.makedirs("/tmp/matplotlib_apex_vto", exist_ok=True)

DEFAULT_SOCKET_PATH = "/tmp/apex_vton_daemon.sock"

def log(tag: str, msg: str):
    print(f"[{tag}] {msg}", flush=True)

_PIPELINE = None
_PIPELINE_LOCK = threading.Lock()

def get_loaded_pipeline(weights_dir: str, device: str = "mps"):
    global _PIPELINE
    with _PIPELINE_LOCK:
        if _PIPELINE is None:
            log("DAEMON INIT", f"Loading TryOnPipeline from {weights_dir} on {device}...")
            from fashn_vton import TryOnPipeline
            t0 = time.time()
            _PIPELINE = TryOnPipeline(weights_dir=weights_dir, device=device)
            t1 = time.time()
            log("DAEMON INIT", f"Pipeline loaded and cached in {t1 - t0:.2f}s")
        return _PIPELINE

def handle_client_connection(client_sock, weights_dir: str, device: str = "mps"):
    file_obj = client_sock.makefile("rwb", buffering=0)
    try:
        line = file_obj.readline()
        if not line:
            return
        
        req = json.loads(line.decode("utf-8"))
        job_id = req.get("job_id", "anonymous")
        person_path = req.get("person")
        garment_path = req.get("garment")
        output_path = req.get("output")
        category = req.get("category", "tops")
        garment_photo_type = req.get("garment_type", "flat-lay")
        num_timesteps = int(req.get("timesteps", 20))
        guidance_scale = float(req.get("guidance_scale", 1.5))
        skip_cfg = int(req.get("skip_cfg", 1))
        debug_dir = req.get("debug_dir")

        def send_event(payload: dict):
            payload["job_id"] = job_id
            raw = json.dumps(payload).encode("utf-8") + b"\n"
            try:
                file_obj.write(raw)
                file_obj.flush()
            except Exception:
                pass

        send_event({
            "type": "progress",
            "stage": "PREPARING",
            "percent": 10,
            "step": 0,
            "total": 0,
            "message": "Preparing your photo..."
        })

        if not os.path.exists(person_path):
            send_event({"type": "failed", "error_code": "INVALID_PERSON_IMAGE", "error_message": "Person image not found."})
            return
        if not os.path.exists(garment_path):
            send_event({"type": "failed", "error_code": "INVALID_GARMENT_IMAGE", "error_message": "Garment image not found."})
            return

        send_event({
            "type": "progress",
            "stage": "GARMENT_VALIDATION",
            "percent": 20,
            "step": 0,
            "total": 0,
            "message": "Validating selected garment..."
        })

        person_img = Image.open(person_path).convert("RGB")
        garment_img = Image.open(garment_path).convert("RGB")

        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)
            person_img.save(os.path.join(debug_dir, "person_input.jpg"), "JPEG", quality=95)
            garment_img.save(os.path.join(debug_dir, "garment_input.jpg"), "JPEG", quality=95)

        pipeline = get_loaded_pipeline(weights_dir, device)

        send_event({
            "type": "progress",
            "stage": "POSE_DETECTION",
            "percent": 30,
            "step": 0,
            "total": 0,
            "message": "Detecting pose..."
        })

        send_event({
            "type": "progress",
            "stage": "GARMENT_PREPARATION",
            "percent": 40,
            "step": 0,
            "total": 0,
            "message": "Preparing garment..."
        })

        t_start = time.time()

        def on_step(s: int, tot: int):
            pct = 40 + int(50 * s / tot)
            send_event({
                "type": "progress",
                "stage": "DIFFUSION",
                "percent": pct,
                "step": s,
                "total": tot,
                "message": "Generating AI try-on..."
            })

        # Run inference protected by lock
        with _PIPELINE_LOCK:
            result = pipeline(
                person_image=person_img,
                garment_image=garment_img,
                category=category,
                garment_photo_type=garment_photo_type,
                num_samples=1,
                num_timesteps=num_timesteps,
                guidance_scale=guidance_scale,
                skip_cfg_last_n_steps=skip_cfg,
                segmentation_free=True,
                progress_callback=on_step
            )

        t_duration = time.time() - t_start

        if not result or not result.images:
            send_event({"type": "failed", "error_code": "VTO_OUTPUT_INVALID", "error_message": "Model generated empty output."})
            return

        send_event({
            "type": "progress",
            "stage": "FINALIZING",
            "percent": 95,
            "step": 0,
            "total": 0,
            "message": "Finalizing result..."
        })

        out_img = result.images[0]
        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        out_img.save(output_path, "JPEG", quality=95)

        if debug_dir:
            out_img.save(os.path.join(debug_dir, "output.jpg"), "JPEG", quality=95)

        send_event({
            "type": "completed",
            "percent": 100,
            "stage": "COMPLETED",
            "output": output_path,
            "duration": round(t_duration, 2),
            "message": "Try-on ready"
        })

    except Exception as e:
        log("DAEMON ERROR", str(e))
        send_event({
            "type": "failed",
            "error_code": "VTO_INFERENCE_FAILED",
            "error_message": f"Inference worker failed: {str(e)}"
        })
    finally:
        try:
            client_sock.close()
        except Exception:
            pass

def run_daemon(socket_path: str, weights_dir: str, device: str = "mps"):
    if os.path.exists(socket_path):
        try:
            os.unlink(socket_path)
        except OSError:
            pass

    log("DAEMON", f"Starting VTON daemon on {socket_path} with device={device}")
    get_loaded_pipeline(weights_dir, device)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(5)
    os.chmod(socket_path, 0o777)
    log("DAEMON", f"Ready and listening for inference requests on {socket_path}")

    try:
        while True:
            client, _ = server.accept()
            handle_client_connection(client, weights_dir, device)
    finally:
        server.close()
        if os.path.exists(socket_path):
            os.unlink(socket_path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VTON Worker Daemon")
    parser.add_argument("--socket", default=DEFAULT_SOCKET_PATH)
    parser.add_argument("--weights-dir", required=True)
    parser.add_argument("--device", default="mps")
    args = parser.parse_args()

    run_daemon(args.socket, args.weights_dir, args.device)
