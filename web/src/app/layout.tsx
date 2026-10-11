import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Bangladesh Climate Risk", template: "%s · Bangladesh Climate Risk" },
  description:
    "One-month-ahead rainfall and drought-risk outlook for Bangladesh divisions, with every past forecast verified against what actually fell.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-line bg-surface">
          <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href="/" className="font-semibold tracking-tight">
              Bangladesh Climate Risk
            </Link>
            <div className="flex gap-5 text-sm text-ink-2">
              <Link href="/" className="hover:text-ink">
                Outlook
              </Link>
              <Link href="/model" className="hover:text-ink">
                Model &amp; accuracy
              </Link>
              <a
                href="https://github.com/Ezazulmahi/climate-risk-bd"
                className="hover:text-ink"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
            </div>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t border-line px-4 py-6 text-center text-xs text-muted">
          Portfolio demo built on ERA5 reanalysis (ECMWF, via Open-Meteo). Not an official forecast.
          For decisions use the{" "}
          <a className="underline" href="https://live6.bmd.gov.bd/" target="_blank" rel="noreferrer">
            Bangladesh Meteorological Department
          </a>
          .
        </footer>
      </body>
    </html>
  );
}
