function el(id){ return document.getElementById(id); }
const ui = { module_mm: el("module_mm"), z1: el("z1"), z2: el("z2"), alpha_deg: el("alpha_deg"),
  face_width_mm: el("face_width_mm"), rpm: el("rpm"), torque_Nm: el("torque_Nm"), Ck: el("Ck"), Cf: el("Cf"), N: el("N"),
  backend_url: el("backend_url"), btnHealth: el("btnHealth"), btnRun: el("btnRun"), status: el("status"),
  kpiPin: el("kpiPin"), kpiPloss: el("kpiPloss"), kpiEta: el("kpiEta"), kpiMu: el("kpiMu"),
  resStatus: el("resStatus"), resMsg: el("resMsg"), resJob: el("resJob"), plotCanvas: el("plotCanvas"),
  backendModeBadge: el("backendModeBadge") };
function fmt(v,d=2){ const n=Number(v); return Number.isFinite(n)?n.toFixed(d):"—"; }
function setStatus(kind,text){ ui.status.className = "status " + (kind || "neutral"); ui.status.textContent = text; }
function readInputs(){ return {
  module_mm: parseFloat(ui.module_mm.value), z1: parseInt(ui.z1.value,10), z2: parseInt(ui.z2.value,10),
  alpha_deg: parseFloat(ui.alpha_deg.value), face_width_mm: parseFloat(ui.face_width_mm.value), rpm: parseFloat(ui.rpm.value),
  torque_Nm: parseFloat(ui.torque_Nm.value), Ck: parseFloat(ui.Ck.value), Cf: parseFloat(ui.Cf.value), N: parseInt(ui.N.value,10),
  source:"GEARCALC-PRO frontend", schema_version:"losses-demo.v1"}; }
function validateInputs(p){
  const req=["module_mm","z1","z2","alpha_deg","face_width_mm","rpm","torque_Nm","Ck","Cf","N"];
  for(const k of req){ if(!Number.isFinite(p[k])) return `Invalid value for ${k}`; }
  if (p.module_mm <= 0) return "module_mm must be > 0";
  if (p.z1 < 3 || p.z2 < 3) return "z1, z2 must be >= 3";
  if (p.alpha_deg <= 0 || p.alpha_deg >= 90) return "alpha_deg must be between 0 and 90";
  if (p.face_width_mm <= 0) return "face_width_mm must be > 0";
  if (p.rpm <= 0) return "rpm must be > 0";
  if (p.torque_Nm <= 0) return "torque_Nm must be > 0";
  if (p.N < 50) return "N must be >= 50";
  return null;
}
async function checkHealth(){
  try{
    const base = ui.backend_url.value.trim().replace(/\/+$/,"");
    setStatus("", "Checking backend health...");
    const r = await fetch(base + "/api/health");
    const data = await r.json();
    if (!r.ok) throw new Error(JSON.stringify(data));
    ui.backendModeBadge.textContent = `Mode: ${data.default_mode || "—"}`;
    setStatus("ok", `Backend OK (${data.service || "service"})`);
  }catch(err){ console.error(err); setStatus("bad", "Backend health check failed: " + (err.message || String(err))); }
}
async function runDemo(){
  const payload = readInputs(); const err = validateInputs(payload); if (err){ setStatus("bad", err); return; }
  try{
    const base = ui.backend_url.value.trim().replace(/\/+$/,"");
    setStatus("", "Calling backend demo... (FastAPI → MATLAB/Python)"); ui.btnRun.disabled = true;
    const r = await fetch(base + "/api/losses-demo", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload) });
    const data = await r.json();
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    if (!data.ok) throw new Error(data.message || "Backend returned error");
    if (data.mode_used) ui.backendModeBadge.textContent = `Mode: ${data.mode_used}`;
    const res = data.results || {};
    ui.kpiPin.textContent = Number.isFinite(res.P_in_W) ? `${fmt(res.P_in_W,2)} W` : "—";
    ui.kpiPloss.textContent = Number.isFinite(res.P_loss_W) ? `${fmt(res.P_loss_W,2)} W` : "—";
    ui.kpiEta.textContent = Number.isFinite(res.efficiency) ? `${fmt(100*res.efficiency,3)} %` : "—";
    ui.kpiMu.textContent = Number.isFinite(res.mu_mean) ? fmt(res.mu_mean,4) : "—";
    ui.resStatus.textContent = data.status || "success"; ui.resMsg.textContent = data.message || "—"; ui.resJob.textContent = data._job_id || "—";
    drawPlot(ui.plotCanvas, res.theta_rad || [], res.P_fric_W || []);
    setStatus("ok", "Backend demo completed successfully.");
  }catch(err){ console.error(err); setStatus("bad", "Backend demo error: " + (err.message || String(err))); }
  finally{ ui.btnRun.disabled = false; }
}
function drawPlot(canvas, xs, ys){
  const ctx = canvas.getContext("2d"), W = canvas.width, H = canvas.height; ctx.clearRect(0,0,W,H);
  ctx.fillStyle = "#0c1322"; ctx.fillRect(0,0,W,H); ctx.fillStyle = "#eaf1ff"; ctx.font = "14px Segoe UI"; ctx.fillText("P_fric demo curve from backend", 12, 20);
  if (!Array.isArray(xs)||!Array.isArray(ys)||xs.length<2||ys.length<2||xs.length!==ys.length){ ctx.fillStyle="#9fb0d2"; ctx.font="13px Segoe UI"; ctx.fillText("No plot data available.",12,46); return; }
  const L=56,R=18,T=34,B=38,w=W-L-R,h=H-T-B; let xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
  if (!(Number.isFinite(xmin)&&Number.isFinite(xmax)&&Number.isFinite(ymin)&&Number.isFinite(ymax))) return;
  if (xmax===xmin) xmax=xmin+1; if (ymax===ymin) ymax=ymin+1; const padY=0.08*(ymax-ymin); ymin-=padY; ymax+=padY;
  const X=x=>L + (x-xmin)/(xmax-xmin)*w, Y=y=>T + (1-(y-ymin)/(ymax-ymin))*h;
  ctx.strokeStyle = "#23304a"; ctx.lineWidth = 1;
  for(let i=0;i<=5;i++){ const yy=T+(i/5)*h; ctx.beginPath(); ctx.moveTo(L,yy); ctx.lineTo(W-R,yy); ctx.stroke(); }
  for(let i=0;i<=6;i++){ const xx=L+(i/6)*w; ctx.beginPath(); ctx.moveTo(xx,T); ctx.lineTo(xx,H-B); ctx.stroke(); }
  ctx.strokeStyle="#31415f"; ctx.strokeRect(L,T,w,h);
  ctx.strokeStyle="#ffd27a"; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(X(xs[0]),Y(ys[0])); for(let i=1;i<xs.length;i++) ctx.lineTo(X(xs[i]),Y(ys[i])); ctx.stroke();
  ctx.fillStyle="#9fb0d2"; ctx.font="12px Segoe UI"; ctx.fillText(`θ [rad]  (${xmin.toFixed(4)} → ${xmax.toFixed(4)})`, L, H-12);
  ctx.save(); ctx.translate(14, T+h/2); ctx.rotate(-Math.PI/2); ctx.fillText(`P_fric [W]  (${ymin.toFixed(2)} → ${ymax.toFixed(2)})`, 0, 0); ctx.restore();
}
ui.btnHealth.addEventListener("click", checkHealth); ui.btnRun.addEventListener("click", runDemo); checkHealth(); drawPlot(ui.plotCanvas, [], []);
