"use client"
import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { UserAvatar } from "./UserAvatar"

// Avatar button that opens a small menu; closes on outside click / Escape.
// `header` = avatar only, menu drops down-right (app header / billing page).
// `sidebar` = avatar + email row, menu pops up (left-nav footer).
export function AccountDropdown({ email, children, variant = "header" }: { email?: string | null; children: React.ReactNode; variant?: "header" | "sidebar" }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const sidebar = variant === "sidebar"

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Account menu"
        className={
          sidebar
            ? "flex w-full items-center gap-2 rounded-lg px-1.5 py-1.5 text-left outline-none transition hover:bg-gray-100 focus-visible:ring-2 focus-visible:ring-indigo-500"
            : "flex items-center rounded-full outline-none transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
        }
      >
        <UserAvatar email={email} />
        {sidebar && email && <span className="min-w-0 flex-1 truncate text-sm text-gray-700">{email}</span>}
      </button>
      {open && (
        <div
          className={
            sidebar
              ? "absolute bottom-full left-0 z-50 mb-2 w-56 overflow-hidden rounded-xl border border-gray-200 bg-white py-1 shadow-lg"
              : "absolute right-0 top-full z-50 mt-2 w-52 overflow-hidden rounded-xl border border-gray-200 bg-white py-1 shadow-lg"
          }
          onClick={() => setOpen(false)}
        >
          {email && (
            <div className="truncate border-b border-gray-100 px-3 py-2 text-xs text-gray-500">{email}</div>
          )}
          {children}
        </div>
      )}
    </div>
  )
}

const itemClass = "block w-full cursor-pointer px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"

export function DropdownLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href} className={itemClass}>{children}</Link>
}

export function DropdownButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return <button onClick={onClick} className={itemClass}>{children}</button>
}
