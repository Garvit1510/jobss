function canvasSig() {
  try {
    const c = document.createElement("canvas");
    c.width = 240;
    c.height = 60;
    const x = c.getContext("2d");
    x.textBaseline = "top";
    x.font = "16px Arial";
    x.fillStyle = "#f60";
    x.fillRect(10, 10, 100, 30);
    x.fillStyle = "#069";
    x.fillText("JobLens AI <device> 1.0", 4, 18);
    return c.toDataURL();
  } catch {
    return "nocanvas";
  }
}

function webglSig() {
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    return ext ? `${gl.getParameter(ext.UNMASKED_VENDOR_WEBGL)}|${gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)}` : "nowebgl";
  } catch {
    return "nowebgl";
  }
}

let cached = null;

export async function getDeviceId() {
  if (cached) return cached;
  const n = window.navigator;
  const parts = [
    n.userAgent, n.platform, n.language, n.hardwareConcurrency, n.deviceMemory, n.maxTouchPoints,
    `${window.screen.width}x${window.screen.height}x${window.screen.colorDepth}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone, canvasSig(), webglSig(),
  ].join("::");
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(parts));
  cached = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 40);
  return cached;
}
