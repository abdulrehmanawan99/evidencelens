"use client";

import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";

export default function PdfReader({ documentId, page, pageCount, onPage }: { documentId: string; page: number; pageCount: number; onPage: (value: number) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [width, setWidth] = useState(600);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(160, entry.contentRect.width)));
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let alive = true;
    let destroy: (() => void) | undefined;
    setPdf(null); setError(""); setLoading(true);
    import("pdfjs-dist/legacy/build/pdf.mjs").then(async (library) => {
      library.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
      const task = library.getDocument({ url: `/api/v1/documents/${documentId}/content`, disableRange: true, enableXfa: false, useWasm: false, stopAtErrors: true, maxImageSize: 8000000, canvasMaxAreaInBytes: 16000000, useSystemFonts: true, standardFontDataUrl: "/pdf-assets/standard_fonts/", cMapUrl: "/pdf-assets/cmaps/", cMapPacked: true });
      destroy = () => { void task.destroy(); };
      const document = await task.promise;
      if (alive) setPdf(document); else void task.destroy();
    }).catch(() => { if (alive) { setError("The original PDF could not be rendered. The extracted passages remain available below."); setLoading(false); } });
    return () => { alive = false; destroy?.(); };
  }, [documentId]);

  useEffect(() => {
    if (!pdf || !canvas.current) return;
    let alive = true;
    let task: RenderTask | undefined;
    setLoading(true); setError("");
    pdf.getPage(Math.max(1, Math.min(page, pdf.numPages))).then(async (documentPage) => {
      if (!alive || !canvas.current) return;
      const original = documentPage.getViewport({ scale: 1 });
      let scale = Math.min(width / original.width, 1.5);
      if (original.width * original.height * scale * scale > 4000000) scale = Math.sqrt(4000000 / (original.width * original.height));
      const viewport = documentPage.getViewport({ scale });
      canvas.current.width = Math.ceil(viewport.width);
      canvas.current.height = Math.ceil(viewport.height);
      task = documentPage.render({ canvas: canvas.current, viewport, annotationMode: 0 });
      await task.promise;
      if (alive) setLoading(false);
    }).catch((cause) => { if (alive && cause?.name !== "RenderingCancelledException") { setLoading(false); setError("This PDF page could not be rendered. Read its extracted text below."); } });
    return () => { alive = false; task?.cancel(); };
  }, [pdf, page, width]);

  return <div className="pdf-viewer" ref={container}>
    <div className="pdf-toolbar"><strong>Original PDF</strong><div><button className="button small" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous PDF page">Previous</button><span aria-live="polite">Page {page} / {pageCount}</span><button className="button small" disabled={page >= pageCount} onClick={() => onPage(page + 1)} aria-label="Next PDF page">Next</button></div></div>
    {loading && <p className="pdf-status" role="status">Rendering source page…</p>}
    {error && <p className="inline-warning" role="alert">{error}</p>}
    <canvas ref={canvas} aria-label={`Original PDF page ${page}`} role="img" style={{ maxWidth: "100%", height: "auto" }} />
    <p className="pdf-caption">Original page above; exact extracted-text citations below. PDF reading order may differ from the visual layout.</p>
  </div>;
}
