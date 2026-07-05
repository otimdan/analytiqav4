"use client"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { useAuthUser } from "@/hooks/useAuthUser"
import { AccountDropdown, DropdownButton } from "./AccountDropdown"

// Avatar + menu for the app header.
export function AccountMenu() {
  const router = useRouter()
  const { user } = useAuthUser()

  async function signOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push("/login")
    router.refresh()
  }

  if (!user) return null

  return (
    <AccountDropdown email={user.email}>
      <DropdownButton onClick={signOut}>Sign out</DropdownButton>
    </AccountDropdown>
  )
}
