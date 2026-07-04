"use client"

function slugify(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "chart"
}

export function ChartCard({ imageBase64, caption }: { imageBase64: string; caption?: string }) {
  const src = `data:image/png;base64,${imageBase64}`
  const filename = `${caption ? slugify(caption) : "chart"}.png`

  return (
    <figure className="mt-3 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
        <figcaption className="truncate text-xs font-medium text-gray-600">
          {caption || "Chart"}
        </figcaption>
        <a
          href={src}
          download={filename}
          title="Download PNG"
          className="flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-50 hover:text-indigo-600"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Download
        </a>
      </div>
      {/* Chart is rendered on the light chart surface (#fcfcfb); center it. */}
      <div className="flex justify-center bg-[#fcfcfb] p-2">
        <img src={src} alt={caption || "Chart"} className="max-h-[520px] w-auto max-w-full" />
      </div>
    </figure>
  )
}
