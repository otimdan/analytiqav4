"use client"
import Link from "next/link"
import { Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"

// Sends the user to the billing page to choose/confirm a plan.
export function UpgradeButton({ size = "sm" }: { size?: "sm" | "default" }) {
  return (
    <Button asChild size={size}>
      <Link href="/billing">
        <Sparkles className="size-4" />
        Upgrade
      </Link>
    </Button>
  )
}
