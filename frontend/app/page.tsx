import Link from "next/link"
import {
  Sparkles, Upload, MessageSquareText, BarChart3, FileText,
  ShieldCheck, ArrowRight, Check,
} from "lucide-react"
import { Button } from "@/components/ui/button"

// NOTE: auth isn't built yet, so CTAs point at the app (/app). Once Supabase
// Auth lands these become /signup and /login.
const START_HREF = "/app"

const FEATURES = [
  {
    icon: MessageSquareText,
    title: "A guided research copilot",
    body: "It doesn't just answer — it proposes the next step and runs it for you on one click. You always know what to do next.",
  },
  {
    icon: ShieldCheck,
    title: "Real statistics, not guesses",
    body: "Assumption checks pick the right test — t-test, ANOVA, chi-square, non-parametric fallbacks — and flag results that look too good to be true.",
  },
  {
    icon: BarChart3,
    title: "Publication-ready charts",
    body: "Ask for “plot X vs Y” and get a clean, correctly-typed chart on a consistent, colorblind-safe theme — downloadable as PNG.",
  },
  {
    icon: FileText,
    title: "Export a full report",
    body: "Turn a session of analyses into a structured write-up — methods, results, and interpretation — ready to hand in or share.",
  },
]

const STEPS = [
  { icon: Upload, title: "Upload your dataset", body: "Drop in a CSV. Analytika profiles every column — types, distributions, missingness — in seconds." },
  { icon: MessageSquareText, title: "Ask in plain language", body: "“Does satisfaction differ by department?” It classifies intent, runs the analysis in a sandbox, and explains the result." },
  { icon: Sparkles, title: "Follow the thread", body: "Accept the suggested next step, track a hypothesis as a project, and watch your analysis build stage by stage." },
]

const TIERS = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    blurb: "For trying it out and light coursework.",
    features: ["3 analyses / month", "Charts & summaries", "1 dataset at a time"],
    cta: "Start free",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$19",
    cadence: "/ month",
    blurb: "For researchers and students doing real work.",
    features: ["200 analyses / month", "Full reports & exports", "Hypothesis / project tracking", "Priority model routing"],
    cta: "Get Pro",
    highlighted: true,
  },
]

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col bg-white text-gray-900">
      {/* Nav */}
      <header className="sticky top-0 z-40 border-b border-gray-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <Sparkles className="size-4" />
            </span>
            Analytika
          </Link>
          <nav className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link href={START_HREF}>Sign in</Link>
            </Button>
            <Button asChild size="sm">
              <Link href={START_HREF}>Get started</Link>
            </Button>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_0%,rgba(79,70,229,0.10),transparent)]" />
          <div className="mx-auto max-w-6xl px-6 py-24 text-center">
            <div className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">
              <Sparkles className="size-3.5" /> AI research analyst
            </div>
            <h1 className="mx-auto max-w-3xl text-balance text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
              Analyze your data like a statistician — <span className="text-indigo-600">without being one</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-gray-600">
              Upload a dataset and get guided statistical analysis, correct tests, clean charts, and a
              write-up — from an AI that walks you through every step.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild size="xl">
                <Link href={START_HREF}>
                  Upload a dataset <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild size="xl" variant="outline">
                <Link href="#how-it-works">See how it works</Link>
              </Button>
            </div>
            <p className="mt-4 text-xs text-gray-400">No credit card required · CSV in, insight out</p>
          </div>
        </section>

        {/* Features */}
        <section className="border-t border-gray-100 bg-gray-50/60">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold tracking-tight">Everything a research assistant should be</h2>
              <p className="mt-3 text-gray-600">Not a chatbot bolted onto pandas — a guided analysis engine.</p>
            </div>
            <div className="mt-12 grid gap-5 sm:grid-cols-2">
              {FEATURES.map((f) => (
                <div key={f.title} className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                  <div className="flex size-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                    <f.icon className="size-5" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-gray-600">{f.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="scroll-mt-16">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold tracking-tight">From CSV to conclusion in three steps</h2>
            </div>
            <div className="mt-12 grid gap-8 md:grid-cols-3">
              {STEPS.map((s, i) => (
                <div key={s.title} className="relative">
                  <div className="flex size-11 items-center justify-center rounded-xl border border-gray-200 bg-white text-indigo-600 shadow-sm">
                    <s.icon className="size-5" />
                  </div>
                  <div className="mt-4 flex items-center gap-2">
                    <span className="text-xs font-bold text-indigo-600">STEP {i + 1}</span>
                  </div>
                  <h3 className="mt-1 text-lg font-semibold">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-gray-600">{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section id="pricing" className="scroll-mt-16 border-t border-gray-100 bg-gray-50/60">
          <div className="mx-auto max-w-5xl px-6 py-20">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold tracking-tight">Simple, honest pricing</h2>
              <p className="mt-3 text-gray-600">Start free. Upgrade when you're doing real work.</p>
            </div>
            <div className="mx-auto mt-12 grid max-w-3xl gap-6 sm:grid-cols-2">
              {TIERS.map((t) => (
                <div
                  key={t.name}
                  className={`relative rounded-2xl border bg-white p-7 ${t.highlighted ? "border-indigo-300 shadow-lg ring-1 ring-indigo-100" : "border-gray-200 shadow-sm"}`}
                >
                  {t.highlighted && (
                    <span className="absolute -top-3 left-7 rounded-full bg-indigo-600 px-3 py-0.5 text-xs font-medium text-white">
                      Most popular
                    </span>
                  )}
                  <h3 className="text-lg font-semibold">{t.name}</h3>
                  <p className="mt-1 text-sm text-gray-500">{t.blurb}</p>
                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-4xl font-bold tracking-tight">{t.price}</span>
                    <span className="text-sm text-gray-500">{t.cadence}</span>
                  </div>
                  <ul className="mt-6 space-y-3">
                    {t.features.map((feat) => (
                      <li key={feat} className="flex items-start gap-2 text-sm text-gray-700">
                        <Check className="mt-0.5 size-4 shrink-0 text-indigo-600" />
                        {feat}
                      </li>
                    ))}
                  </ul>
                  <Button asChild className="mt-7 w-full" variant={t.highlighted ? "default" : "outline"}>
                    <Link href={START_HREF}>{t.cta}</Link>
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="mx-auto max-w-6xl px-6 py-24">
          <div className="overflow-hidden rounded-3xl bg-indigo-600 px-8 py-16 text-center text-white">
            <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
              Bring your dataset. We'll bring the statistician.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-indigo-100">
              Your first analyses are on us. See what a guided AI analyst does with your data.
            </p>
            <Button asChild size="xl" variant="secondary" className="mt-8 bg-white text-indigo-700 hover:bg-indigo-50">
              <Link href={START_HREF}>
                Get started free <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-100">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 text-sm text-gray-500 sm:flex-row">
          <div className="flex items-center gap-2 font-medium text-gray-700">
            <span className="flex size-6 items-center justify-center rounded-md bg-indigo-600 text-white">
              <Sparkles className="size-3.5" />
            </span>
            Analytika
          </div>
          <p>© {new Date().getFullYear()} Analytika. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
