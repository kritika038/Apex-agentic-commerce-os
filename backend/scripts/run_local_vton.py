#!/usr/bin/env python3
"""
Dedicated Local FASHN VTON v1.5 Inference Worker.
Executes inside vto_venv (Python 3.12) on Apple Silicon (MPS) or CUDA.
Emits unbuffered lifecycle progress logs and debug artifacts.
"""

import sys
import os
import argparse
import time
from pathlib import Path
from PIL import Image

# Ensure fashn-vton-1.5/src is in sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_src = os.path.abspath(os.path.join(script_dir, "../fashn-vton-1.5/src"))
if os.path.exists(repo_src) and repo_src not in sys.path:
    sys.path.insert(0, repo_src)

# Disable noisy telemetry and set writable mpl config dir if needed
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib_apex_vto")
os.makedirs("/tmp/matplotlib_apex_vto", exist_ok=True)

def log(tag: str, msg: str):
    print(f"[{tag}] {msg}", flush=True)

try:
    from fashn_vton import TryOnPipeline
except ImportError as e:
    log("ERROR", f"Failed to import fashn_vton: {e}")
    sys.exit(2)

_PIPELINE_CACHE = {}

def get_pipeline(weights_dir: str, device: str):
    key = (os.path.abspath(weights_dir), str(device))
    if key not in _PIPELINE_CACHE:
        log("PIPELINE LOAD", f"Initializing TryOnPipeline from {weights_dir} on {device}...")
        t0 = time.time()
        _PIPELINE_CACHE[key] = TryOnPipeline(weights_dir=weights_dir, device=device)
        t1 = time.time()
        log("PIPELINE LOAD", f"Pipeline initialized in {t1 - t0:.2f}s")
    return _PIPELINE_CACHE[key]

def emit_progress(stage: str, percent: int, step: int, total: int, msg: str):
    print(f"[PROGRESS] STAGE={stage}|PERCENT={percent}|STEP={step}|TOTAL={total}|MSG={msg}", flush=True)

def run_inference(
    person_image_path: str,
    garment_image_path: str,
    output_image_path: str,
    weights_dir: str,
    category: str = "tops",
    garment_photo_type: str = "flat-lay",
    num_timesteps: int = 20,
    guidance_scale: float = 1.5,
    skip_cfg_last_n_steps: int = 1,
    segmentation_free: bool = True,
    device: str = "mps",
    debug_dir: str = None
):
    log("WORKER START", f"Inference requested: category={category}, type={garment_photo_type}, timesteps={num_timesteps}, device={device}")
    emit_progress("PREPARING", 10, 0, 0, "Preparing your photo...")
    
    if not os.path.exists(person_image_path):
        raise FileNotFoundError(f"Person image not found: {person_image_path}")
    if not os.path.exists(garment_image_path):
        raise FileNotFoundError(f"Garment image not found: {garment_image_path}")
    if not os.path.exists(weights_dir):
        raise FileNotFoundError(f"Weights dir not found: {weights_dir}")

    emit_progress("GARMENT_VALIDATION", 20, 0, 0, "Validating selected garment...")
    log("IMAGE LOAD", f"Loading person ({person_image_path}) and garment ({garment_image_path})...")
    person_img = Image.open(person_image_path).convert("RGB")
    garment_img = Image.open(garment_image_path).convert("RGB")
    log("IMAGE LOAD", f"Person dimensions: {person_img.size}, Garment dimensions: {garment_img.size}")

    # Save local debug artifacts if debug_dir is provided
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        debug_person = os.path.join(debug_dir, "person_input.jpg")
        debug_garment = os.path.join(debug_dir, "garment_input.jpg")
        person_img.save(debug_person, "JPEG", quality=95)
        garment_img.save(debug_garment, "JPEG", quality=95)
        log("DEBUG ARTIFACT", f"Saved debug inputs to {debug_person} and {debug_garment}")

    pipeline = get_pipeline(weights_dir=weights_dir, device=device)

    emit_progress("POSE_DETECTION", 30, 0, 0, "Detecting pose...")
    log("PREPROCESSING", "Executing pose detection and human segmentation...")
    
    emit_progress("GARMENT_PREPARATION", 40, 0, 0, "Preparing garment...")
    log("INFERENCE START", f"Running diffusion sampling ({num_timesteps} steps, guidance={guidance_scale})...")
    t_start = time.time()

    def step_callback(step: int, total: int):
        pct = 40 + int(50 * step / total)
        emit_progress("DIFFUSION", pct, step, total, "Generating AI try-on...")

    result = pipeline(
        person_image=person_img,
        garment_image=garment_img,
        category=category,
        garment_photo_type=garment_photo_type,
        num_samples=1,
        num_timesteps=num_timesteps,
        guidance_scale=guidance_scale,
        skip_cfg_last_n_steps=skip_cfg_last_n_steps,
        segmentation_free=segmentation_free,
        progress_callback=step_callback
    )
    t_end = time.time()
    log("INFERENCE COMPLETE", f"Diffusion sampling finished in {t_end - t_start:.2f}s")

    if not result or not result.images:
        raise RuntimeError("Model returned an empty images list")

    emit_progress("FINALIZING", 95, 0, 0, "Finalizing result...")
    out_img = result.images[0]
    out_dir = os.path.dirname(os.path.abspath(output_image_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    out_img.save(output_image_path, "JPEG", quality=95)
    log("OUTPUT SAVE", f"Saved output to {output_image_path} (dimensions: {out_img.size})")

    if debug_dir:
        debug_output = os.path.join(debug_dir, "output.jpg")
        out_img.save(debug_output, "JPEG", quality=95)
        log("DEBUG ARTIFACT", f"Saved debug output to {debug_output}")

    emit_progress("COMPLETED", 100, num_timesteps, num_timesteps, "Try-on ready")
    log("WORKER EXIT", f"Total execution completed in {time.time() - t_start:.2f}s")

def main():
    parser = argparse.ArgumentParser(description="Run local FASHN VTON v1.5 inference")
    parser.add_argument("--person", required=True, help="Path to person image")
    parser.add_argument("--garment", required=True, help="Path to garment image")
    parser.add_argument("--output", required=True, help="Path to output image")
    parser.add_argument("--weights-dir", required=True, help="Path to weights directory")
    parser.add_argument("--category", default="tops", choices=["tops", "bottoms", "one-pieces"])
    parser.add_argument("--garment-type", default="flat-lay", choices=["flat-lay", "model"])
    parser.add_argument("--timesteps", type=int, default=30)
    parser.add_argument("--guidance-scale", type=float, default=1.5)
    parser.add_argument("--skip-cfg", type=int, default=1)
    parser.add_argument("--segmentation-free", action="store_true", default=True)
    parser.add_argument("--no-segmentation-free", action="store_false", dest="segmentation_free")
    parser.add_argument("--device", default="mps")
    parser.add_argument("--debug-dir", default=None, help="Directory to save debug artifacts")

    args = parser.parse_args()
    try:
        run_inference(
            person_image_path=args.person,
            garment_image_path=args.garment,
            output_image_path=args.output,
            weights_dir=args.weights_dir,
            category=args.category,
            garment_photo_type=args.garment_type,
            num_timesteps=args.timesteps,
            guidance_scale=args.guidance_scale,
            skip_cfg_last_n_steps=args.skip_cfg,
            segmentation_free=args.segmentation_free,
            device=args.device,
            debug_dir=args.debug_dir
        )
    except Exception as e:
        log("ERROR", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
