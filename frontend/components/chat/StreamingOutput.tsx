"use client"
export function StreamingOutput({ isVisible }: { isVisible: boolean }) {
  if (!isVisible) return null
  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-1.5 w-1.5 rounded-full bg-indigo-400"
            style={{ animation: "bounce 1.2s infinite", animationDelay: `${i * 0.2}s` }} />
        ))}
      </div>
      <span className="text-xs text-gray-400">Analysing…</span>
      <style>{`@keyframes bounce { 0%, 80%, 100% { transform: translateY(0); } 40% { transform: translateY(-4px); } }`}</style>
    </div>
  )
}
