"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { LogOut } from "lucide-react"
import { createClient } from "@/lib/supabase/client"
import { Button } from "@/components/ui/button"

// Small account indicator + sign-out for the app header.
export function AccountMenu() {
  const router = useRouter()
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null))
  }, [])

  async function signOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push("/login")
    router.refresh()
  }

  if (!email) return null

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-xs text-gray-500 sm:inline">{email}</span>
      <Button variant="ghost" size="sm" onClick={signOut} title="Sign out" className="text-gray-500">
        <LogOut className="size-4" />
        <span className="hidden sm:inline">Sign out</span>
      </Button>
    </div>
  )
}
