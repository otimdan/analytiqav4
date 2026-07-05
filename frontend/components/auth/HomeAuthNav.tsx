"use client"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { useAuthUser } from "@/hooks/useAuthUser"
import { Button } from "@/components/ui/button"
import { AccountDropdown, DropdownLink, DropdownButton } from "./AccountDropdown"

// Homepage nav: signed out shows Sign in / Get started; signed in shows an avatar.
export function HomeAuthNav() {
  const { user, loading } = useAuthUser()
  const router = useRouter()

  async function signOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.refresh()
  }

  // Reserve space while resolving to avoid a flash of the wrong state.
  if (loading) return <div className="h-8 w-8" />

  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link href="/login">Sign in</Link>
        </Button>
        <Button asChild size="sm">
          <Link href="/signup">Get started</Link>
        </Button>
      </div>
    )
  }

  return (
    <AccountDropdown email={user.email}>
      <DropdownLink href="/app">Go to app</DropdownLink>
      <DropdownButton onClick={signOut}>Sign out</DropdownButton>
    </AccountDropdown>
  )
}
