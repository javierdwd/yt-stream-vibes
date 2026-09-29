import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service · yt-stream-vibes",
  description:
    "Terms of Service for yt-stream-vibes, including YouTube API Services user obligations.",
};

const updated = "September 29, 2026";

export default function TermsPage() {
  return (
    <main className="h-full min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
      <div className="mx-auto max-w-3xl space-y-8 pb-12">
        <header className="space-y-3 border-b border-border pb-6">
          <Link
            href="/"
            className="font-mono text-[10px] uppercase tracking-widest text-muted transition-colors duration-200 hover:text-accent"
          >
            ← Back
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight text-fg md:text-3xl">
            Terms of Service
          </h1>
          <p className="font-mono text-xs text-muted">Last updated: {updated}</p>
        </header>

        <Section title="1. Agreement">
          <p>
            These Terms of Service (“Terms”) govern your access to and use of
            yt-stream-vibes (the “Service”). By accessing or using the Service,
            you agree to these Terms and to our{" "}
            <Link
              href="/privacy"
              className="text-accent underline-offset-2 hover:underline"
            >
              Privacy Policy
            </Link>
            . If you do not agree, do not use the Service.
          </p>
        </Section>

        <Section title="2. The Service">
          <p>
            yt-stream-vibes is a real-time dashboard that helps you discover
            YouTube Live streams, view public live chat, and review derived
            sentiment / intent / hype analytics for an active analysis session.
            Features may change, be limited, or be unavailable without notice.
          </p>
        </Section>

        <Section title="3. YouTube API Services">
          <p>
            The Service uses{" "}
            <strong className="font-medium text-fg">YouTube API Services</strong>.
            By using yt-stream-vibes, you also agree to be bound by the{" "}
            <Ext href="https://www.youtube.com/t/terms">
              YouTube Terms of Service
            </Ext>
            .
          </p>
          <p>Please also review:</p>
          <ul className="list-disc space-y-2 pl-5 text-muted">
            <li>
              <Ext href="https://www.youtube.com/t/terms">
                YouTube Terms of Service
              </Ext>
            </li>
            <li>
              <Ext href="https://policies.google.com/privacy">
                Google Privacy Policy
              </Ext>
            </li>
            <li>
              <Ext href="https://developers.google.com/youtube/terms/api-services-terms-of-service">
                YouTube API Services Terms of Service
              </Ext>
            </li>
            <li>
              <Ext href="https://developers.google.com/youtube/terms/developer-policies">
                YouTube API Services Developer Policies
              </Ext>
            </li>
          </ul>
          <p>
            YouTube content and branding shown in the Service remain subject to
            YouTube’s and Google’s rights and policies. We do not claim ownership
            of YouTube content surfaced through the API.
          </p>
        </Section>

        <Section title="4. Acceptable use">
          <p>You agree not to use the Service to:</p>
          <ul className="list-disc space-y-2 pl-5 text-muted">
            <li>Violate applicable law or third-party rights.</li>
            <li>
              Abuse, overload, or interfere with YouTube API Services, our
              infrastructure, or other users.
            </li>
            <li>
              Attempt unauthorized access to accounts, streams, or systems you do
              not control.
            </li>
            <li>
              Misrepresent the Service as an official YouTube or Google product.
            </li>
            <li>
              Scrape, redistribute, or commercially exploit YouTube content beyond
              what these Terms and YouTube’s terms allow.
            </li>
          </ul>
        </Section>

        <Section title="5. No account required (MVP)">
          <p>
            The current MVP does not require a yt-stream-vibes user account.
            Analysis sessions are temporary and held in memory. You are
            responsible for how you use the Service and for any stream URLs or
            queries you submit.
          </p>
        </Section>

        <Section title="6. Disclaimers">
          <p>
            The Service is provided “as is” and “as available”, without warranties
            of any kind, express or implied. We do not warrant uninterrupted
            access, accurate classifications, or continued availability of
            YouTube API Services. Analytics outputs are informational only and
            are not professional advice.
          </p>
        </Section>

        <Section title="7. Limitation of liability">
          <p>
            To the maximum extent permitted by law, we are not liable for any
            indirect, incidental, special, consequential, or punitive damages, or
            any loss of data, profits, or goodwill, arising from your use of the
            Service or from YouTube / third-party content.
          </p>
        </Section>

        <Section title="8. Changes">
          <p>
            We may update these Terms from time to time. The “Last updated” date
            will change when we do. Continued use of the Service after an update
            constitutes acceptance of the revised Terms.
          </p>
        </Section>

        <Section title="9. Contact">
          <p>
            Questions about these Terms:{" "}
            <a
              href="mailto:javierdwd@gmail.com?subject=yt-stream-vibes%20terms"
              className="text-accent underline-offset-2 hover:underline"
            >
              javierdwd@gmail.com
            </a>
            .
          </p>
        </Section>
      </div>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight text-fg">{title}</h2>
      <div className="space-y-3 text-sm leading-relaxed text-muted">{children}</div>
    </section>
  );
}

function Ext({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent underline-offset-2 hover:underline"
    >
      {children}
    </a>
  );
}
