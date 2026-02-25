from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
import subprocess
import pathlib
import json
import os
import uuid
import time
import math

app = FastAPI(title="GEARCALC-PRO Backend API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # local dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name, str(int(default))).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}

def to_dict_model(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj.dict()

class LossesDemoInput(BaseModel):
    module_mm: float = Field(..., gt=0)
    z1: int = Field(..., ge=3)
    z2: int = Field(..., ge=3)
    alpha_deg: float = Field(..., gt=0, lt=90)
    Ck: float = Field(1.0, gt=0)
    Cf: float = Field(1.25, gt=0)
    rpm: float = Field(..., gt=0)
    torque_Nm: float = Field(..., gt=0)
    face_width_mm: float = Field(..., gt=0)
    N: int = Field(1200, ge=50)
    source: Optional[str] = "GEARCALC-PRO frontend"
    schema_version: Optional[str] = "losses-demo.v1"

def run_python_model(py_script: pathlib.Path, py_in_path: pathlib.Path, py_out_path: pathlib.Path):
    if not py_script.exists():
        raise RuntimeError(f"Python model script not found: {py_script}")
    python_exe = os.getenv("PYTHON_EXE", "python")
    proc = subprocess.run(
        [python_exe, str(py_script), "--input", str(py_in_path), "--output", str(py_out_path)],
        capture_output=True, text=True, timeout=120
    )
    if proc.returncode != 0:
        raise RuntimeError("Python model failed.\nSTDOUT:\n%s\nSTDERR:\n%s" % (proc.stdout[-4000:], proc.stderr[-4000:]))
    if not py_out_path.exists():
        raise RuntimeError("Python model did not produce output JSON.")

def build_py_input(inp: LossesDemoInput) -> Dict[str, Any]:
    m = float(inp.module_mm); z1 = int(inp.z1); z2 = int(inp.z2)
    alpha_deg = float(inp.alpha_deg)
    rpm = float(inp.rpm); torque = float(inp.torque_Nm)
    r1_mm = 0.5 * z1 * m; r1_m = r1_mm * 1e-3
    omega = 2.0 * math.pi * rpm / 60.0
    P_in = omega * torque
    pitchline_speed = omega * r1_m
    return {
        "module_mm": m, "z1": z1, "z2": z2, "alpha_deg": alpha_deg, "rpm": rpm, "torque_Nm": torque,
        "face_width_mm": float(inp.face_width_mm), "Ck": float(inp.Ck), "Cf": float(inp.Cf), "N": int(inp.N),
        "P_in_W": P_in, "pitchline_speed_mps": pitchline_speed, "features_version": "losses-demo.features.v1"
    }

def wrap_response_from_py(inp: LossesDemoInput, py_res: Dict[str, Any], mode_used: str) -> Dict[str, Any]:
    P_in = float(py_res.get("P_in_W_override", build_py_input(inp)["P_in_W"]))
    P_loss = float(py_res.get("P_loss_W", 0.0))
    eta = max(0.0, min(1.0, 1.0 - P_loss / max(P_in, 1e-12)))
    return {
        "ok": True,
        "status": "success",
        "message": f"Losses demo computed via {mode_used}",
        "schema_version": "losses-demo.response.v1",
        "mode_used": mode_used,
        "inputs": {
            "module_mm": float(inp.module_mm), "z1": int(inp.z1), "z2": int(inp.z2), "alpha_deg": float(inp.alpha_deg),
            "rpm": float(inp.rpm), "torque_Nm": float(inp.torque_Nm), "face_width_mm": float(inp.face_width_mm),
            "Ck": float(inp.Ck), "Cf": float(inp.Cf), "N": int(inp.N)
        },
        "results": {
            "P_in_W": P_in, "P_loss_W": P_loss, "efficiency": eta, "mu_mean": py_res.get("mu_mean", None),
            "theta_rad": py_res.get("theta_rad", []), "P_fric_W": py_res.get("P_fric_W", []), "notes": py_res.get("notes", "")
        }
    }

def run_matlab_pipeline(job_dir: pathlib.Path, inp: LossesDemoInput) -> Dict[str, Any]:
    backend_dir = pathlib.Path(__file__).resolve().parent
    matlab_dir = backend_dir / "matlab"
    output_json = job_dir / "output.json"
    input_json = job_dir / "input.json"
    py_models_dir = backend_dir / "py_models"
    with open(input_json, "w", encoding="utf-8") as f:
        json.dump(to_dict_model(inp), f, ensure_ascii=False, indent=2)

    matlab_exe = os.getenv("MATLAB_EXE", "matlab")
    in_path = str(input_json.resolve()).replace("\\", "/")
    out_path = str(output_json.resolve()).replace("\\", "/")
    py_dir = str(py_models_dir.resolve()).replace("\\", "/")
    m_dir = str(matlab_dir.resolve()).replace("\\", "/")
    matlab_cmd = f"addpath('{m_dir}'); gearcalc_losses_demo('{in_path}','{out_path}','{py_dir}');"

    proc = subprocess.run([matlab_exe, "-batch", matlab_cmd], capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError("MATLAB wrapper failed.\nSTDOUT:\n%s\nSTDERR:\n%s" % (proc.stdout[-4000:], proc.stderr[-4000:]))
    if not output_json.exists():
        raise RuntimeError("MATLAB completed but output.json was not produced.")
    with open(output_json, "r", encoding="utf-8") as f:
        out = json.load(f)
    return out

def run_python_only_pipeline(job_dir: pathlib.Path, inp: LossesDemoInput) -> Dict[str, Any]:
    backend_dir = pathlib.Path(__file__).resolve().parent
    py_script = backend_dir / "py_models" / "loss_nn_demo.py"
    py_in_path = job_dir / "py_in.json"
    py_out_path = job_dir / "py_out.json"
    py_in = build_py_input(inp)
    with open(py_in_path, "w", encoding="utf-8") as f:
        json.dump(py_in, f, ensure_ascii=False, indent=2)
    run_python_model(py_script, py_in_path, py_out_path)
    with open(py_out_path, "r", encoding="utf-8") as f:
        py_res = json.load(f)
    return wrap_response_from_py(inp, py_res, mode_used="python-only demo")

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "GEARCALC-PRO backend",
        "version": app.version,
        "default_mode": "matlab" if env_flag("USE_MATLAB", False) else "python-only"
    }

@app.post("/api/losses-demo")
def losses_demo(inp: LossesDemoInput):
    backend_dir = pathlib.Path(__file__).resolve().parent
    tmp_root = backend_dir / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    job_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    job_dir = tmp_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    use_matlab = env_flag("USE_MATLAB", False)

    try:
        out = run_matlab_pipeline(job_dir, inp) if use_matlab else run_python_only_pipeline(job_dir, inp)
        if not isinstance(out, dict):
            raise RuntimeError("Invalid backend output type (expected JSON object).")
        out["_job_id"] = job_id
        return out
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Computation timed out.")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Executable not found: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
