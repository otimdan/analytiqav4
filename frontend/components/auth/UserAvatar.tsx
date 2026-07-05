import { cn } from "@/lib/utils"

export function UserAvatar({ email, className }: { email?: string | null; className?: string }) {
  const initial = (email?.trim()?.[0] || "?").toUpperCase()
  return (
    <span
      className={cn(
        "flex size-8 items-center justify-center rounded-full bg-indigo-600 text-sm font-semibold text-white select-none",
        className
      )}
    >
      {initial}
    </span>
  )
}
