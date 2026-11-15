// Fotografía un modelo con model-viewer (el mismo visor del sitio) usando Chrome sin ventana.
// Uso: node capturas.mjs <id> [--poster]
//   Genera herramientas/capturas/<id>-<animación>.png: hoja con 3 ángulos (filas) x 4 momentos (columnas).
//   Con --poster también guarda modelos/<id>-poster.webp con fondo transparente.
import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { extname, join, normalize, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(AQUI, "..");
const id = process.argv[2];
const conPoster = process.argv.includes("--poster");
if (!id) { console.error("Uso: node capturas.mjs <id> [--poster]"); process.exit(1); }

const ANGULOS = [["3/4 frente", "40deg 72deg auto"], ["costado", "90deg 78deg auto"], ["3/4 atrás", "215deg 70deg auto"]];
const W = 420, H = 315;

const pagina = `<!doctype html><html><head><meta charset="utf-8">
<script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js"></script>
<style>body{margin:0;background:#fff} model-viewer{width:${W}px;height:${H}px;background:transparent}</style></head>
<body><model-viewer id="mv" src="/modelos/${id}.glb" shadow-intensity="1" interaction-prompt="none" animation-crossfade-duration="0"></model-viewer></body></html>`;

const tipos = { ".glb": "model/gltf-binary", ".html": "text/html", ".js": "text/javascript", ".webp": "image/webp", ".png": "image/png" };
const servidor = createServer(async (req, res) => {
  const ruta = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (ruta === "/__captura.html") { res.writeHead(200, { "content-type": "text/html" }); return res.end(pagina); }
  const archivo = normalize(join(RAIZ, ruta));
  if (!archivo.startsWith(RAIZ)) { res.writeHead(403); return res.end(); }
  try { const d = await readFile(archivo); res.writeHead(200, { "content-type": tipos[extname(archivo)] || "application/octet-stream" }); res.end(d); }
  catch { res.writeHead(404); res.end(); }
}).listen(0);
const puerto = servidor.address().port;

const navegador = await chromium.launch({ channel: "chrome", headless: true, args: ["--enable-gpu", "--ignore-gpu-blocklist"] });
const pag = await navegador.newPage({ viewport: { width: W, height: H } });
const errores = [];
pag.on("pageerror", (e) => errores.push(String(e)));
pag.on("console", (m) => { if (m.type() === "error") errores.push(m.text()); });
await pag.goto(`http://localhost:${puerto}/__captura.html`);
await pag.waitForFunction(() => document.getElementById("mv")?.loaded === true, null, { timeout: 120000 });

const info = await pag.evaluate(async () => {
  const mv = document.getElementById("mv");
  return { animaciones: mv.availableAnimations, dims: (() => { const d = mv.getDimensions(); return [d.x, d.y, d.z]; })() };
});
console.log(`${id}: medidas ${info.dims.map((v) => v.toFixed(2)).join(" x ")} m (ancho x alto x largo), animaciones: ${info.animaciones.join(", ")}`);

// Toma una foto: animación (o null = pose de la escultura), momento (fracción) y órbita de cámara.
async function foto(anim, frac, orbita, tipo = "image/png") {
  return pag.evaluate(async ({ anim, frac, orbita, tipo }) => {
    const mv = document.getElementById("mv");
    const cuadro = () => new Promise((r) => requestAnimationFrame(() => r()));
    mv.cameraOrbit = orbita; mv.fieldOfView = "auto"; mv.jumpCameraToGoal();
    if (anim) {
      if (mv.animationName !== anim) {
        mv.animationName = anim;
        await mv.updateComplete;              // el cambio de animación se aplica en el ciclo siguiente
        mv.play(); await cuadro(); await cuadro();
      }
      mv.pause(); mv.currentTime = frac * mv.duration;
    } else { mv.pause(); mv.animationName = null; await mv.updateComplete; mv.currentTime = 0; }
    await mv.updateComplete;
    for (let i = 0; i < 6; i++) await cuadro();
    return mv.toDataURL(tipo, 0.92);
  }, { anim, frac, orbita, tipo });
}

// Arma una hoja: filas = ángulos, columnas = momentos.
async function hoja(titulo, imagenes, filas, columnas, etiquetasFila, etiquetasCol) {
  return pag.evaluate(async ({ titulo, imagenes, filas, columnas, etiquetasFila, etiquetasCol, W, H }) => {
    const c = document.createElement("canvas"); const top = 34;
    c.width = columnas * W; c.height = filas * H + top;
    const g = c.getContext("2d");
    g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);
    g.fillStyle = "#222"; g.font = "bold 20px sans-serif"; g.fillText(titulo, 10, 24);
    for (let i = 0; i < imagenes.length; i++) {
      const im = new Image(); im.src = imagenes[i]; await im.decode();
      const f = Math.floor(i / columnas), k = i % columnas;
      g.drawImage(im, k * W, top + f * H, W, H);
      g.strokeStyle = "#ddd"; g.strokeRect(k * W, top + f * H, W, H);
      g.fillStyle = "#555"; g.font = "13px sans-serif";
      g.fillText(`${etiquetasFila[f]} · ${etiquetasCol[k]}`, k * W + 6, top + f * H + 16);
    }
    return c.toDataURL("image/png");
  }, { titulo, imagenes, filas, columnas, etiquetasFila, etiquetasCol, W, H });
}

const guardar = async (ruta, dataUrl) => writeFile(ruta, Buffer.from(dataUrl.split(",")[1], "base64"));
const dirCapturas = join(AQUI, "capturas");
await mkdir(dirCapturas, { recursive: true });

// pose de la escultura (sin animación)
{
  const ims = [];
  for (const [, orb] of ANGULOS) ims.push(await foto(null, 0, orb));
  await guardar(join(dirCapturas, `${id}-pose.png`), await hoja(`${id} — pose de la escultura`, ims, 1, 3, ["pose"], ANGULOS.map((a) => a[0])));
}
const MOMENTOS = [0, 0.25, 0.5, 0.75];
for (const anim of info.animaciones) {
  const ims = [];
  for (const [, orb] of ANGULOS) for (const fr of MOMENTOS) ims.push(await foto(anim, fr, orb));
  await guardar(join(dirCapturas, `${id}-${anim}.png`),
    await hoja(`${id} — ${anim}`, ims, ANGULOS.length, MOMENTOS.length, ANGULOS.map((a) => a[0]), MOMENTOS.map((m) => `${Math.round(m * 100)}%`)));
  console.log(`  hoja ${id}-${anim}.png`);
}

if (conPoster) {
  await pag.setViewportSize({ width: 920, height: 608 });
  await pag.evaluate(() => { const mv = document.getElementById("mv"); mv.style.width = "920px"; mv.style.height = "608px"; });
  const url = await foto(null, 0, "0deg 75deg 105%", "image/webp");
  await guardar(join(RAIZ, "modelos", `${id}-poster.webp`), url);
  console.log(`  póster modelos/${id}-poster.webp`);
}

if (errores.length) console.log("Errores en la consola:\n  " + errores.join("\n  "));
await navegador.close();
servidor.close();
