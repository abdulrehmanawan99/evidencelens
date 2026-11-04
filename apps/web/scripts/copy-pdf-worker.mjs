import { cp, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
await mkdir(path.join(root, "public/pdf-assets"), { recursive: true });
await cp(path.join(root, "node_modules/pdfjs-dist/legacy/build/pdf.worker.min.mjs"), path.join(root, "public/pdf.worker.min.mjs"));
for (const directory of ["standard_fonts", "cmaps"]) {
  await cp(path.join(root, "node_modules/pdfjs-dist", directory), path.join(root, "public/pdf-assets", directory), { recursive: true });
}
