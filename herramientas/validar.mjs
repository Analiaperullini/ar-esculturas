// Valida modelos .glb con gltf-validator (el validador oficial de Khronos).
// Uso: node validar.mjs ../modelos/hadrosaurio.glb [otro.glb ...]
// Sale con código 1 si algún archivo tiene errores.
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import validator from "gltf-validator";

let hayErrores = false;
for (const archivo of process.argv.slice(2)) {
  const datos = new Uint8Array(await readFile(archivo));
  const r = await validator.validateBytes(datos, { maxIssues: 200 });
  const { numErrors, numWarnings, numInfos, messages } = r.issues;
  console.log(`${basename(archivo)}: ${numErrors} errores, ${numWarnings} advertencias, ${numInfos} avisos`);
  for (const m of messages.filter((m) => m.severity <= 1)) {
    console.log(`  [${m.severity === 0 ? "ERROR" : "advertencia"}] ${m.code}: ${m.message} (${m.pointer || ""})`);
  }
  const info = r.info || {};
  console.log(`  ${info.drawCallCount ?? "?"} draw calls, ${info.totalVertexCount ?? "?"} vértices, ${info.totalTriangleCount ?? "?"} triángulos, animaciones: ${info.animationCount ?? 0}`);
  if (numErrors > 0) hayErrores = true;
}
process.exit(hayErrores ? 1 : 0);
