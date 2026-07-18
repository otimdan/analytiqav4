import type { Metadata } from "next"
import "./globals.css"
import { Providers } from "./providers"

export const metadata: Metadata = {
  title: "Analytika — AI research data analysis",
  description: "Upload a dataset and get guided statistical analysis, charts, and reports from an AI research analyst.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      {/* The full-screen scroll lock the chat app needs lives in app/app/layout.tsx,
          so marketing/auth pages at the root can scroll normally. */}
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
