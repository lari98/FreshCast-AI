import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "FreshCast AI",
  description: "Demand forecasting and expiry-aware replenishment for fresh goods (demo).",
};

/**
 * Content-Security-Policy as a meta tag, because a static export has no server to
 * send headers (a CDN response-headers policy should send the same text plus
 * frame-ancestors). It blocks scripts, styles and connections to any other site, so
 * injected code could neither load a payload nor send data out. Next.js needs inline
 * scripts for hydration, hence 'unsafe-inline' for scripts; this is weaker than a
 * nonce-based policy and is documented as such in docs/security.
 */
function csp(): string {
  const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"; // same default as lib/source.ts
  let apiOrigin = "";
  try {
    apiOrigin = api ? new URL(api).origin : "";
  } catch {
    /* an invalid URL means no extra origin is allowed */
  }
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src 'self' ${apiOrigin}`.trim(),
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
  ].join("; ");
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de">
      {process.env.NODE_ENV === "production" && (
        <head>
          <meta httpEquiv="Content-Security-Policy" content={csp()} />
          <meta name="referrer" content="no-referrer" />
        </head>
      )}
      <body>{children}</body>
    </html>
  );
}
