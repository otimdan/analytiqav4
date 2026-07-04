import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Analytika",
  description: "AI-powered research data analysis",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen overflow-hidden bg-white antialiased">
        {children}
      </body>
    </html>
  )
}
