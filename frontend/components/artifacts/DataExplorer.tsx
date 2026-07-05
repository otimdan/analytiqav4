"use client"
import { useState, useEffect, useCallback } from "react"
import type { ChartImage, StreamChunk } from "@/lib/types"

type ReportInfo = NonNullable<StreamChunk["report"]>

interface DataExplorerProps {
  datasetFilename: string | null
  rowCount?: number | null
  images: ChartImage[]
  reports: ReportInfo[]
}

// Right rail: artifacts grouped into Files / Charts & Images / Reports, with a
// full-screen preview when a chart is expanded. Collapses to a thin strip.
export function DataExplorer({ datasetFilename, rowCount, images, reports }: DataExplorerProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [previewIndex, setPreviewIndex] = useState<number | null>(null)

  if (collapsed) {
    return (
      <div className="flex w-11 shrink-0 flex-col items-center gap-4 border-l border-gray-100 bg-gray-50/60 py-4">
        <button onClick={() => setCollapsed(false)} title="Open data explorer" className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
          <PanelIcon />
        </button>
        {images.length > 0 && <Badge icon={<ChartIcon />} count={images.length} />}
        {reports.length > 0 && <Badge icon={<ReportIcon />} count={reports.length} />}
      </div>
    )
  }

  return (
    <>
      <aside className="flex w-72 shrink-0 flex-col overflow-y-auto border-l border-gray-100 bg-gray-50/60">
        <div className="flex items-center justify-between px-4 py-3">
          <span className="flex items-center gap-2 text-sm font-semibold text-gray-700">
            <GridIcon /> Data Explorer
          </span>
          <button onClick={() => setCollapsed(true)} title="Collapse" className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
            <PanelIcon />
          </button>
        </div>

        <Section title="Files">
          {datasetFilename ? (
            <div className="flex items-center gap-2.5 rounded-lg border border-gray-200 bg-white px-3 py-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-green-50 text-green-600"><SpreadsheetIcon /></span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-gray-800">{datasetFilename}</span>
                <span className="block text-[11px] text-gray-400">Spreadsheet{rowCount != null ? ` · ${rowCount} rows` : ""}</span>
              </span>
            </div>
          ) : <Empty>No files yet.</Empty>}
        </Section>

        <Section title="Charts & Images" count={images.length}>
          {images.length ? (
            <div className="grid grid-cols-2 gap-2">
              {images.map((img, i) => (
                <button
                  key={i}
                  onClick={() => setPreviewIndex(i)}
                  className="group overflow-hidden rounded-lg border border-gray-200 bg-white transition-shadow hover:shadow-md"
                  title={img.caption || `Chart ${i + 1}`}
                >
                  <img src={`data:image/png;base64,${img.src}`} alt={img.caption || `Chart ${i + 1}`} className="h-20 w-full bg-[#fcfcfb] object-contain" />
                  {img.caption && <span className="block truncate px-1.5 py-1 text-left text-[10px] text-gray-500">{img.caption}</span>}
                </button>
              ))}
            </div>
          ) : <Empty>Charts will appear here.</Empty>}
        </Section>

        <Section title="Reports" count={reports.length}>
          {reports.length ? (
            <div className="flex flex-col gap-2">
              {reports.map((r, i) => (
                <a
                  key={i}
                  href={`data:text/markdown;charset=utf-8,${encodeURIComponent(r.markdown)}`}
                  download={r.filename}
                  className="flex items-center gap-2.5 rounded-lg border border-gray-200 bg-white px-3 py-2.5 transition-colors hover:bg-gray-50"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600"><ReportIcon /></span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-gray-800">{r.filename}</span>
                    <span className="block text-[11px] text-gray-400">{r.artifact_count} artifacts · {r.stages_covered.length} stages</span>
                  </span>
                </a>
              ))}
            </div>
          ) : <Empty>Generated reports will appear here.</Empty>}
        </Section>
      </aside>

      {previewIndex != null && images[previewIndex] && (
        <ImagePreview
          images={images}
          index={previewIndex}
          onClose={() => setPreviewIndex(null)}
          onNavigate={setPreviewIndex}
        />
      )}
    </>
  )
}

function ImagePreview({ images, index, onClose, onNavigate }: { images: ChartImage[]; index: number; onClose: () => void; onNavigate: (i: number) => void }) {
  const prev = useCallback(() => onNavigate((index - 1 + images.length) % images.length), [index, images.length, onNavigate])
  const next = useCallback(() => onNavigate((index + 1) % images.length), [index, images.length, onNavigate])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
      else if (e.key === "ArrowLeft") prev()
      else if (e.key === "ArrowRight") next()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [onClose, prev, next])

  const img = images[index]
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6" onClick={onClose}>
      <div className="flex max-h-full w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-4 py-3">
          <span className="truncate text-sm font-medium text-gray-700">{img.caption || `Chart ${index + 1} of ${images.length}`}</span>
          <div className="flex items-center gap-1">
            <a href={`data:image/png;base64,${img.src}`} download={`${(img.caption || "chart").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`} title="Download PNG" className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-indigo-600"><DownloadIcon /></a>
            <button onClick={onClose} title="Close" className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"><CloseIcon /></button>
          </div>
        </div>
        <div className="relative flex flex-1 items-center justify-center overflow-auto bg-[#fcfcfb] p-4">
          {images.length > 1 && (
            <button onClick={prev} title="Previous" className="absolute left-2 rounded-full bg-white/80 p-2 text-gray-600 shadow hover:bg-white"><ChevronLeftIcon /></button>
          )}
          <img src={`data:image/png;base64,${img.src}`} alt={img.caption || "Chart"} className="max-h-[70vh] w-auto max-w-full" />
          {images.length > 1 && (
            <button onClick={next} title="Next" className="absolute right-2 rounded-full bg-white/80 p-2 text-gray-600 shadow hover:bg-white"><ChevronRightIcon /></button>
          )}
        </div>
      </div>
    </div>
  )
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <div className="border-t border-gray-100 px-4 py-3">
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
        {title}
        {count != null && count > 0 && <span className="rounded-full bg-gray-200 px-1.5 text-[10px] font-medium text-gray-500">{count}</span>}
      </p>
      {children}
    </div>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-gray-400">{children}</p>
}

function Badge({ icon, count }: { icon: React.ReactNode; count: number }) {
  return (
    <span className="relative text-gray-400">
      {icon}
      <span className="absolute -right-1.5 -top-1.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-indigo-600 px-1 text-[9px] font-semibold text-white">{count}</span>
    </span>
  )
}

/* icons */
function GridIcon() { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></svg> }
function PanelIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="15" y1="3" x2="15" y2="21" /></svg> }
function SpreadsheetIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" /></svg> }
function ChartIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg> }
function ReportIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="16" y2="17" /></svg> }
function DownloadIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg> }
function CloseIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg> }
function ChevronLeftIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6" /></svg> }
function ChevronRightIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6" /></svg> }
