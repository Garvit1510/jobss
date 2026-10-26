// In-browser proctoring vision using @vladmandic/human (single tfjs instance).
// Detects faces (count + identity embedding) and COCO objects (phones, laptops, extra people).
import Human from "@vladmandic/human";

const config = {
  modelBasePath: "/models/",
  cacheModels: true,
  backend: "webgl",
  warmup: "none",
  debug: false,
  filter: { enabled: false },
  face: {
    enabled: true,
    detector: { maxDetected: 5, minConfidence: 0.35, rotation: false, return: false },
    mesh: { enabled: true },
    iris: { enabled: false },
    description: { enabled: true },
    emotion: { enabled: false },
    antispoof: { enabled: false },
    liveness: { enabled: false },
  },
  object: { enabled: true },
  body: { enabled: false },
  hand: { enabled: false },
  gesture: { enabled: false },
  segmentation: { enabled: false },
};

// Objects that should not be in frame during a proctored test.
const DEVICE_LABELS = { "cell phone": "phone", "laptop": "second screen", tv: "screen", monitor: "screen", remote: "remote", book: "book/notes", tablet: "tablet" };

let human = null;
let loadPromise = null;

export function getHuman() {
  if (!human) human = new Human(config);
  return human;
}

export async function loadVision() {
  const h = getHuman();
  if (!loadPromise) {
    loadPromise = (async () => {
      await h.load();
      await h.warmup();
    })();
  }
  await loadPromise;
  return h;
}

export async function detect(video) {
  const h = getHuman();
  const res = await h.detect(video);
  const faces = (res.face || []).filter((f) => (f.score || f.boxScore || f.faceScore || 0) > 0.4);
  const embeddings = faces.map((f) => f.embedding).filter((e) => Array.isArray(e) && e.length);
  const objects = res.object || [];
  const devices = [...new Set(objects.filter((o) => o.score > 0.45 && DEVICE_LABELS[o.label]).map((o) => DEVICE_LABELS[o.label]))];
  const personCount = objects.filter((o) => o.label === "person" && o.score > 0.55).length;
  const angle = faces[0]?.rotation?.angle || null; // { roll, yaw, pitch } radians
  return { faceCount: faces.length, personCount, devices, embedding: embeddings[0] || null, embeddings, angle };
}

// best similarity (0..1) of a live frame's faces against the registered reference.
// Returns null if no valid comparison could be made (never treat that as a mismatch).
export function bestMatch(ref, embeddings) {
  if (!ref || !embeddings?.length) return null;
  let best = null;
  for (const e of embeddings) {
    const sim = similarity(ref, e);
    if (sim != null) best = best == null ? sim : Math.max(best, sim);
  }
  return best;
}

export function similarity(a, b) {
  try {
    const s = getHuman().match.similarity(a, b);
    return typeof s === "number" && !Number.isNaN(s) ? s : null;
  } catch {
    return null;
  }
}
