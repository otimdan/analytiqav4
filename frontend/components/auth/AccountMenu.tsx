"use client"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { createPortalSession } from "@/lib/api"
import { useAuthUser } from "@/hooks/useAuthUser"
import { AccountDropdown, DropdownButton } from "./AccountDropdown"

// Avatar + menu for the app header. Pro users get a "Manage subscription" link
// into the Dodo customer portal (view/cancel).
export function AccountMenu({ plan }: { plan?: string }) {
  const router = useRouter()
  const { user } = useAuthUser()

  async function signOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push("/login")
    router.refresh()
  }

  async function manageSubscription() {
    try {
      const { portal_url } = await createPortalSession()
      window.location.href = portal_url
    } catch {
      // no subscription / billing not configured — nothing to open
    }
  }

  if (!user) return null

  return (
    <AccountDropdown email={user.email}>
      {plan === "pro" && (
        <DropdownButton onClick={manageSubscription}>Manage subscription</DropdownButton>
      )}
      <DropdownButton onClick={signOut}>Sign out</DropdownButton>
    </AccountDropdown>
  )
}
