import { createClient } from "./client"

// Returns an Authorization header carrying the current Supabase access token,
// or an empty object when signed out / not configured. Attached to every call
// to the FastAPI backend so it can verify the user.
export async function authHeader(): Promise<Record<string, string>> {
  try {
    const supabase = createClient()
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}
