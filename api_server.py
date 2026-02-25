from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import matlab.engine
import matlab
import math
from typing import Any

app = FastAPI(title="GEARCALC-PRO MATLAB API", version="0.1.0")

# Αν frontend και backend τρέχουν σε διαφορετικό port/domain:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # για dev. Στο production βάλε συγκεκριμένο domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

eng = None

class ContactRatioRequest(BaseModel):
    m: float = Field(gt=0)
    alpha_deg: float = Field(gt=0, lt=90)
    z1: int = Field(ge=3)
    z2: int = Field(ge=3)
    Ck: float = Field(gt=0)
    Cf: float = Field(gt=0)
    N: int = Field(ge=200)

def matlab_to_py(obj: Any):
    """Recursive converter for common MATLAB Engine return types."""
    # matlab.double / numeric arrays
    if isinstance(obj, matlab.double):
        # matlab.double is nested list-like
        data = list(obj)
        # flatten 1xN / Nx1 if possible
        if len(data) == 1:
            return [float(x) for x in data[0]]
        # Nx1 column vector
        if all(isinstance(r, list) and len(r) == 1 for r in data):
            return [float(r[0]) for r in data]
        # general matrix
        return [[float(x) for x in row] for row in data]

    # matlab logical arrays may appear depending on output
    try:
        import matlab.mlarray
        if isinstance(obj, matlab.mlarray.double):
            data = list(obj)
            return data
    except Exception:
        pass

    # dict-like MATLAB struct often becomes python dict-like via engine
    if isinstance(obj, dict):
        return {k: matlab_to_py(v) for k, v in obj.items()}

    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [matlab_to_py(v) for v in obj]

    # plain scalar
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj

    # fallback
    try:
        return float(obj)
    except Exception:
        return str(obj)

@app.on_event("startup")
def startup_event():
    global eng
    eng = matlab.engine.start_matlab()

    # Βάλε εδώ τον φάκελο που έχει το gear_contact_ratio_spur.m
    # π.χ. eng.addpath(r"C:\Users\ioann\Documents\GEARCALC-PRO\matlab", nargout=0)
    eng.addpath(eng.pwd(), nargout=0)

@app.on_event("shutdown")
def shutdown_event():
    global eng
    if eng is not None:
        eng.quit()
        eng = None

@app.get("/health")
def health():
    return {"ok": True, "service": "GEARCALC-PRO MATLAB API"}

@app.post("/api/v1/contact-ratio")
def contact_ratio(req: ContactRatioRequest):
    global eng
    if eng is None:
        raise HTTPException(status_code=500, detail="MATLAB engine is not running.")

    try:
        # Call MATLAB function
        out = eng.gear_contact_ratio_spur(
            float(req.m),
            float(req.alpha_deg),
            int(req.z1),
            int(req.z2),
            float(req.Ck),
            float(req.Cf),
            int(req.N),
            nargout=1
        )

        out_py = matlab_to_py(out)

        # Αν το MATLAB γύρισε ok=false
        if isinstance(out_py, dict) and (not out_py.get("ok", True)):
            raise HTTPException(status_code=400, detail=out_py.get("message", "MATLAB error"))

        return out_py

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server/MATLAB error: {e}")
