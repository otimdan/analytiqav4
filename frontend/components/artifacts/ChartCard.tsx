"use client"
export function ChartCard({ imageBase64, caption }: { imageBase64: string; caption?: string }) {
  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-gray-200 bg-white">
      <img src={`data:image/png;base64,${imageBase64}`} alt={caption || "Chart"} className="w-full" />
      {caption && <p className="px-3 py-2 text-xs text-gray-500">{caption}</p>}
    </div>
  )
}
