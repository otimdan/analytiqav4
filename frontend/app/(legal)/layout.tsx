import Link from "next/link"
import { Sparkles } from "lucide-react"

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <header className="border-b border-gray-100">
        <div className="mx-auto flex h-16 max-w-3xl items-center px-6">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <Sparkles className="size-4" />
            </span>
            Analytika
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-12 [&_h1]:text-3xl [&_h1]:font-bold [&_h1]:tracking-tight [&_h2]:mt-8 [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_p]:mt-3 [&_p]:text-sm [&_p]:leading-relaxed [&_p]:text-gray-600 [&_li]:text-sm [&_li]:text-gray-600 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5 [&_a]:text-indigo-600 [&_a]:underline">
        {children}
      </main>
      <footer className="border-t border-gray-100">
        <div className="mx-auto flex max-w-3xl items-center gap-4 px-6 py-6 text-xs text-gray-400">
          <Link href="/" className="hover:text-gray-600">Home</Link>
          <Link href="/privacy" className="hover:text-gray-600">Privacy</Link>
          <Link href="/terms" className="hover:text-gray-600">Terms</Link>
        </div>
      </footer>
    </div>
  )
}
