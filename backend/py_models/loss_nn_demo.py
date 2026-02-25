import argparse
import json
import math
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    with open(in_path, "r", encoding="utf-8") as f:
        inp = json.load(f)

    rpm = float(inp["rpm"]); torque = float(inp["torque_Nm"]); m = float(inp["module_mm"])
    z1 = int(inp["z1"]); z2 = int(inp["z2"]); alpha_deg = float(inp["alpha_deg"])
    P_in = float(inp["P_in_W"]); b = float(inp.get("face_width_mm", 30.0))
    Ck = float(inp.get("Ck", 1.0)); Cf = float(inp.get("Cf", 1.25)); N = int(inp.get("N", 1200))

    base = 0.018 * P_in
    ratio = max(z2 / max(z1, 1), 1.0)
    geom_factor = 1.0 + 0.012 * abs(ratio - 2.0) + 0.0015 * abs(m - 3.0)
    angle_factor = 1.0 + 0.0025 * abs(alpha_deg - 20.0)
    load_factor = 1.0 + 0.00035 * max(0.0, torque - 300.0)
    speed_factor = 1.0 + 0.00008 * max(0.0, rpm - 3000.0)
    width_factor = 1.0 - 0.0008 * (b - 30.0)
    width_factor = max(0.90, min(1.10, width_factor))
    coeff_factor = (0.95 + 0.05*Ck) * (0.90 + 0.08*Cf)

    P_loss = max(0.0, float(base * geom_factor * angle_factor * load_factor * speed_factor * width_factor * coeff_factor))
    mu_mean = min(0.12, max(0.02, 0.040 + 0.0000055 * rpm + 0.00002 * torque + 0.002*(Cf-1.25)))

    npts = min(max(100, N // 8), 300)
    theta = [(-0.025 + 0.050*i/(npts-1)) for i in range(npts)]
    P_fric = []
    for th in theta:
        xi = (th - theta[0]) / (theta[-1] - theta[0] + 1e-12)
        shape = 0.55 + 0.55 * abs(math.sin(math.pi * xi))
        asym = 1.0 + 0.10*(xi - 0.5)
        ripple = 1.0 + 0.04*math.sin(4.0*math.pi*xi)
        P_fric.append(float(P_loss) * shape * asym * ripple)

    out = {
        "ok": True,
        "P_loss_W": float(P_loss),
        "mu_mean": float(mu_mean),
        "theta_rad": theta,
        "P_fric_W": P_fric,
        "P_in_W_override": float(P_in),
        "notes": "Demo placeholder model. Replace with trained NN inference."
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
