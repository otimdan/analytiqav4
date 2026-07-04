export const metadata = { title: "Privacy Policy — Analytika" }

export default function PrivacyPage() {
  return (
    <article>
      <h1>Privacy Policy</h1>
      <p><strong>Last updated:</strong> July 2026</p>
      <p>
        This Privacy Policy explains what information Analytika (&quot;we&quot;, &quot;us&quot;) collects when
        you use our data-analysis service, how we use it, and the choices you have.
      </p>

      <h2>Information we collect</h2>
      <ul>
        <li><strong>Account information</strong> — the email address you sign up with, managed through our authentication provider.</li>
        <li><strong>Data you upload</strong> — the datasets (e.g. CSV files) you provide, and the analyses, charts, and messages generated from them.</li>
        <li><strong>Usage information</strong> — counts of analyses you run and basic technical logs needed to operate and secure the service.</li>
      </ul>

      <h2>How we use your information</h2>
      <ul>
        <li>To provide the service — running your analyses and returning results.</li>
        <li>To enforce plan limits and process subscriptions.</li>
        <li>To maintain security, prevent abuse, and debug problems.</li>
      </ul>

      <h2>Third-party processors</h2>
      <p>
        We rely on trusted third parties to operate the service, and your data may be processed by them for that purpose:
      </p>
      <ul>
        <li><strong>Supabase</strong> — authentication and database storage.</li>
        <li><strong>Fireworks AI</strong> — large-language-model inference used to interpret requests and narrate results.</li>
        <li><strong>E2B</strong> — secure sandboxes where analysis code runs against your dataset.</li>
        <li><strong>Dodo Payments</strong> — payment processing for subscriptions (as merchant of record).</li>
      </ul>

      <h2>Data retention</h2>
      <p>
        We retain your account and analysis data while your account is active. You may request deletion of your
        account and associated data at any time by contacting us.
      </p>

      <h2>Security</h2>
      <p>
        We use industry-standard measures to protect your data, including authentication, access controls, and
        encrypted connections. No method of transmission or storage is completely secure, however.
      </p>

      <h2>Your rights</h2>
      <p>
        Depending on your location, you may have rights to access, correct, export, or delete your personal data.
        To exercise these, contact us at the address below.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about this policy? Email <a href="mailto:support@analytika.app">support@analytika.app</a>.
      </p>

      <p style={{ marginTop: 32, fontSize: 12, color: "#9ca3af" }}>
        This document is a starting template and should be reviewed by a qualified professional before you rely on it in production.
      </p>
    </article>
  )
}
