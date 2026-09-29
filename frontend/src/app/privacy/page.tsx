import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy · yt-stream-vibes",
  description:
    "Privacy Policy for yt-stream-vibes, including YouTube API Services disclosures and data deletion.",
};

const updated = "September 29, 2026";

export default function PrivacyPage() {
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
            Privacy Policy
          </h1>
          <p className="font-mono text-xs text-muted">Last updated: {updated}</p>
        </header>

        <Section title="1. Overview">
          <p>
            yt-stream-vibes (“Service”, “we”, “us”) is a real-time dashboard that
            discovers YouTube Live streams, ingests public live chat, and
            classifies chat messages for sentiment, intent, and hype signals.
            This Privacy Policy explains what information we process, how YouTube
            API Services are involved, and how you can request deletion of data.
          </p>
          <p>
            By using the Service, you agree to this Privacy Policy and, where
            applicable, to the{" "}
            <Ext href="https://www.youtube.com/t/terms">
              YouTube Terms of Service
            </Ext>
            .
          </p>
        </Section>

        <Section title="2. YouTube API Services">
          <p>
            The Service uses{" "}
            <strong className="font-medium text-fg">YouTube API Services</strong>{" "}
            (including the YouTube Data API) to search for live streams and
            retrieve public stream metadata such as titles, channel names,
            thumbnails, and concurrent viewer counts. Live chat may be read from
            publicly available chat endpoints associated with a selected stream.
          </p>
          <p>
            Pages that display YouTube content include YouTube branding /
            attribution in accordance with the{" "}
            <Ext href="https://developers.google.com/youtube/terms/branding-guidelines">
              YouTube API Services Branding Guidelines
            </Ext>
            .
          </p>
          <p>
            Use of YouTube API Services through yt-stream-vibes is also subject
            to Google’s policies. Please review:
          </p>
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
          </ul>
        </Section>

        <Section title="3. Information we process">
          <p>Depending on how you use the Service, we may process:</p>
          <ul className="list-disc space-y-2 pl-5 text-muted">
            <li>
              <span className="text-fg">Search queries</span> you enter to find
              live streams.
            </li>
            <li>
              <span className="text-fg">Public YouTube stream metadata</span>{" "}
              returned by YouTube API Services (for example video ID, title,
              channel, thumbnail URL, and concurrent viewers).
            </li>
            <li>
              <span className="text-fg">Public live chat messages</span> from a
              stream you choose to analyze, including message text and public
              author display information exposed by the chat source.
            </li>
            <li>
              <span className="text-fg">Derived analytics</span> produced by our
              classifiers (sentiment, intent, hype score, and related session
              metrics).
            </li>
            <li>
              <span className="text-fg">Technical session identifiers</span>{" "}
              needed to keep an analysis session running while you are connected.
            </li>
          </ul>
          <p>
            We do not require you to sign in with a Google or YouTube account to
            use the basic dashboard. We do not sell personal information.
          </p>
        </Section>

        <Section title="4. How we use information">
          <p>We use the information above solely to:</p>
          <ul className="list-disc space-y-2 pl-5 text-muted">
            <li>Show matching live streams and stream cards.</li>
            <li>Connect to the stream you select and display live chat.</li>
            <li>
              Compute and stream real-time vibe / sentiment / Q&amp;A analytics
              for your active session.
            </li>
            <li>Operate, secure, and debug the Service.</li>
          </ul>
        </Section>

        <Section title="5. Storage and retention">
          <p>
            The MVP is designed without a durable user database. Analysis
            sessions and derived metrics are held in memory for the active
            session and are discarded when the session ends, the connection is
            cleared, the process restarts, or idle timeouts apply. We do not
            intentionally keep a long-term archive of chat messages or
            classifications.
          </p>
          <p>
            Your browser may keep ordinary technical data (for example temporary
            client state). You can clear that through your browser settings.
          </p>
        </Section>

        <Section title="6. Data deletion policy">
          <p>
            You can delete or stop processing of session data in these ways:
          </p>
          <ul className="list-disc space-y-2 pl-5 text-muted">
            <li>
              <span className="text-fg">End the analysis session</span> from the
              dashboard (disconnect / clear session). This stops chat ingest and
              removes the in-memory session data on our side.
            </li>
            <li>
              <span className="text-fg">Leave or close the page</span>. Idle or
              disconnected sessions are torn down and associated in-memory data
              is discarded.
            </li>
            <li>
              <span className="text-fg">Clear browser data</span> for this site
              to remove any local client state stored in your browser.
            </li>
            <li>
              <span className="text-fg">Deletion request</span>: if you believe
              we still hold residual data related to your use of the Service,
              email a deletion request to{" "}
              <a
                href="mailto:javierdwd@gmail.com?subject=yt-stream-vibes%20data%20deletion%20request"
                className="text-accent underline-offset-2 hover:underline"
              >
                javierdwd@gmail.com
              </a>{" "}
              (or open an issue on the{" "}
              <Ext href="https://github.com/javierdwd/yt-stream-vibes/issues">
                project repository
              </Ext>
              ). We will confirm and complete deletion of any residual personal
              data we control within a reasonable period, typically within 30
              days, unless a limited retention is required for security or legal
              reasons.
            </li>
          </ul>
          <p>
            If in the future the Service stores Google account authorization
            tokens, you may also revoke the app’s access from your{" "}
            <Ext href="https://myaccount.google.com/permissions">
              Google Account permissions
            </Ext>{" "}
            page.
          </p>
        </Section>

        <Section title="7. Sharing">
          <p>
            We do not sell your personal information. Limited processing may
            occur through infrastructure providers that host the Service, and
            through Google/YouTube when the Service calls YouTube API Services.
            Those parties process data under their own terms and privacy
            policies, including the{" "}
            <Ext href="https://policies.google.com/privacy">
              Google Privacy Policy
            </Ext>
            .
          </p>
        </Section>

        <Section title="8. Third-party links and embedded content">
          <p>
            The Service may link to or embed YouTube content. Your interactions
            with YouTube are governed by YouTube’s and Google’s policies, not
            solely by this Privacy Policy.
          </p>
        </Section>

        <Section title="9. Children">
          <p>
            The Service is not directed to children under 13, and we do not
            knowingly collect personal information from children.
          </p>
        </Section>

        <Section title="10. Changes">
          <p>
            We may update this Privacy Policy from time to time. The “Last
            updated” date at the top of this page will change when we do. Continued
            use of the Service after an update constitutes acceptance of the
            revised policy.
          </p>
        </Section>

        <Section title="11. Contact">
          <p>
            Questions about this Privacy Policy or data deletion requests:{" "}
            <a
              href="mailto:javierdwd@gmail.com?subject=yt-stream-vibes%20privacy"
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
