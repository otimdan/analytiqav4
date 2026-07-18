"use client"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { useAuthUser } from "@/hooks/useAuthUser"
import { AccountDropdown, DropdownLink, DropdownButton } from "./AccountDropdown"

// Avatar + menu for the app header / billing page / sidebar footer.
export function AccountMenu({ variant = "header" }: { variant?: "header" | "sidebar" }) {
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
    <AccountDropdown email={user.email} variant={variant}>
      <DropdownLink href="/billing">Plan &amp; billing</DropdownLink>
      <DropdownButton onClick={signOut}>Sign out</DropdownButton>
    </AccountDropdown>
  )
}
