import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'

const EFFECTIVE_DATE = 'March 22, 2026'
const COMPANY = 'MAS-AI Technologies Inc.'
const JURISDICTION = 'Ontario, Canada'
const CONTACT_EMAIL = 'privacy@mas-ai.co'

export function PrivacyPage() {
  usePageTitle('Privacy Policy')

  return (
    <div className="min-h-screen bg-midnight-900 text-starlight-200">
      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* Back link */}
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 text-sm text-starlight-400 hover:text-starlight-200 transition-colors mb-8"
        >
          <ArrowLeft size={14} />
          Back
        </Link>

        <h1 className="font-display text-3xl font-bold text-starlight-100 mb-2">Privacy Policy</h1>
        <p className="text-sm text-starlight-400 mb-10">Effective: {EFFECTIVE_DATE}</p>

        <div className="space-y-8 text-sm leading-relaxed text-starlight-300">
          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">1. Introduction</h2>
            <p>
              {COMPANY} ("we," "us," or "our") operates Daena, a governed multi-agent AI orchestration platform.
              This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you
              use our Service. Please read this policy carefully. If you do not agree with the terms of this policy,
              please do not access the Service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">2. Information We Collect</h2>

            <h3 className="text-base font-medium text-starlight-200 mb-2 mt-4">2.1 Information You Provide</h3>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong>Account information:</strong> Name, email address, organization name, and encrypted password hash when you register.</li>
              <li><strong>Chat content:</strong> Messages, prompts, and instructions you send to AI models through the Service.</li>
              <li><strong>Preferences:</strong> Settings, model selections, governance configurations, and other customizations.</li>
              <li><strong>Communications:</strong> Emails or messages you send to us for support or feedback.</li>
            </ul>

            <h3 className="text-base font-medium text-starlight-200 mb-2 mt-4">2.2 Information Collected Automatically</h3>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong>Usage data:</strong> Features used, pages visited, session duration, and interaction patterns.</li>
              <li><strong>Device information:</strong> Browser type, operating system, IP address, and device identifiers.</li>
              <li><strong>Governance logs:</strong> Audit trails of AI decisions, model selections, cost records, and approval actions.</li>
              <li><strong>Performance data:</strong> Response times, error rates, and model performance metrics.</li>
            </ul>

            <h3 className="text-base font-medium text-starlight-200 mb-2 mt-4">2.3 Information from Third Parties</h3>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong>OAuth providers:</strong> If you sign in via Google or GitHub, we receive your name, email, and profile picture as authorized by you.</li>
              <li><strong>AI model providers:</strong> Response data, token usage, and error information from third-party model APIs.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">3. How We Use Your Information</h2>
            <ul className="list-disc pl-5 space-y-2">
              <li>To provide, maintain, and improve the Service.</li>
              <li>To authenticate your identity and manage your account.</li>
              <li>To process your AI requests and route them to appropriate model providers.</li>
              <li>To maintain governance audit trails and compliance records.</li>
              <li>To monitor and prevent security threats, fraud, and abuse.</li>
              <li>To communicate with you about the Service, updates, and support.</li>
              <li>To comply with legal obligations.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">4. Data Sharing and Disclosure</h2>
            <p className="font-medium text-starlight-100 mb-2">We do not sell your personal information.</p>
            <p>We may share your information in the following circumstances:</p>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li>
                <strong>AI model providers:</strong> Your prompts and messages are sent to third-party AI model providers
                (such as OpenAI, Anthropic, Google, etc.) to generate responses. These providers process your data
                according to their own privacy policies.
              </li>
              <li>
                <strong>Service providers:</strong> We use trusted third-party services for hosting, analytics, and
                infrastructure that may process your data on our behalf.
              </li>
              <li>
                <strong>Legal requirements:</strong> We may disclose information if required by law, subpoena, or
                government request, or to protect our rights, property, or safety.
              </li>
              <li>
                <strong>Business transfers:</strong> In the event of a merger, acquisition, or asset sale, your
                information may be transferred as part of that transaction.
              </li>
              <li>
                <strong>With your consent:</strong> We may share information for any other purpose with your explicit consent.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">5. Data Security</h2>
            <p>We implement industry-standard security measures, including:</p>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li>AES-256 encryption for sensitive data at rest.</li>
              <li>TLS 1.3 encryption for data in transit.</li>
              <li>JWT-based authentication with short-lived access tokens and rotating refresh tokens.</li>
              <li>Bcrypt password hashing with per-user salts.</li>
              <li>Multi-tenant data isolation (each organization's data is logically separated).</li>
              <li>Prompt injection scanning on all AI inputs.</li>
              <li>Tamper-evident governance audit logs.</li>
            </ul>
            <p className="mt-3">
              While we strive to protect your data, no method of transmission over the Internet or electronic
              storage is 100% secure. We cannot guarantee absolute security.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">6. Data Retention</h2>
            <ul className="list-disc pl-5 space-y-2">
              <li>Account data is retained for the duration of your account and for 30 days after deletion request.</li>
              <li>Chat messages follow the NBMF tiered memory system: ephemeral data (1 hour), working memory (7 days), project memory (1 year), institutional memory (permanent with governance approval).</li>
              <li>Governance audit logs are retained for a minimum of 7 years for compliance purposes.</li>
              <li>Usage and performance data is retained in aggregate form and anonymized after 90 days.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">7. Your Rights</h2>
            <p>Subject to applicable law, you have the right to:</p>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li><strong>Access:</strong> Request a copy of the personal data we hold about you.</li>
              <li><strong>Correction:</strong> Request correction of inaccurate or incomplete personal data.</li>
              <li><strong>Deletion:</strong> Request deletion of your personal data, subject to legal retention requirements.</li>
              <li><strong>Portability:</strong> Request your data in a machine-readable format.</li>
              <li><strong>Restriction:</strong> Request that we restrict processing of your personal data.</li>
              <li><strong>Objection:</strong> Object to processing of your personal data for certain purposes.</li>
              <li><strong>Withdrawal of consent:</strong> Withdraw consent at any time where processing is based on consent.</li>
            </ul>
            <p className="mt-3">
              To exercise these rights, contact us at{' '}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary-400 hover:text-primary-500 underline">{CONTACT_EMAIL}</a>.
              We will respond within 30 days.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">8. Cookies and Tracking</h2>
            <p>
              We use essential cookies for authentication (JWT tokens stored in secure, httpOnly cookies or localStorage).
              We do not use third-party advertising cookies or cross-site tracking.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">9. Children's Privacy</h2>
            <p>
              The Service is not intended for users under the age of 18. We do not knowingly collect personal
              information from children. If we learn that we have collected personal information from a child
              under 18, we will delete that information promptly.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">10. International Data Transfers</h2>
            <p>
              Your information may be transferred to and processed in countries other than {JURISDICTION}, including
              countries where third-party AI model providers operate. We ensure appropriate safeguards are in place
              for such transfers in compliance with applicable data protection laws.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">11. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify you of material changes by posting
              the new Privacy Policy on this page with an updated effective date. Your continued use of the Service
              after changes constitutes acceptance of the revised policy.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-starlight-100 mb-3">12. Contact Us</h2>
            <p>
              If you have questions about this Privacy Policy, please contact:{' '}
            </p>
            <div className="mt-3 p-4 rounded-lg bg-midnight-300/30 border border-white/5">
              <p className="text-starlight-200 font-medium">{COMPANY}</p>
              <p className="text-starlight-400 mt-1">{JURISDICTION}</p>
              <p className="mt-1">
                <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary-400 hover:text-primary-500 underline">{CONTACT_EMAIL}</a>
              </p>
            </div>
          </section>

          <div className="border-t border-white/5 pt-6 mt-10">
            <p className="text-xs text-starlight-500">
              {COMPANY} &middot; {JURISDICTION} &middot; {EFFECTIVE_DATE}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PrivacyPage
