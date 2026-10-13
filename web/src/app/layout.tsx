import type { Metadata } from "next";
import Link from "next/link";
import LangToggle from "@/components/LangToggle";
import { getDict } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Bangladesh Climate Risk", template: "%s · Bangladesh Climate Risk" },
  description:
    "Rainfall, drought, heat and dengue outlooks for Bangladesh, a 64-district drought monitor, and a public record of every forecast against what actually happened.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const { lang, t } = await getDict();
  const nav = [
    ["/", t.navOutlook],
    ["/monitor", t.navMonitor],
    ["/dengue", t.navDengue],
    ["/insurance", t.navInsurance],
    ["/model", t.navModel],
    ["/data", t.navApi],
  ] as const;
  return (
    <html lang={lang} className="h-full antialiased">
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-line bg-surface">
          <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href="/" className="font-semibold tracking-tight">
              {t.site}
            </Link>
            {/* Phones: title + language on one row, links in a scrollable row below. */}
            <div className="order-last -mx-4 flex w-[calc(100%+2rem)] gap-x-5 overflow-x-auto whitespace-nowrap px-4 pb-1 text-sm text-ink-2 md:order-none md:mx-0 md:w-auto md:flex-1 md:flex-wrap md:overflow-visible md:px-0 md:pb-0">
              {nav.map(([href, label]) => (
                <Link key={href} href={href} className="hover:text-ink">
                  {label}
                </Link>
              ))}
              <a
                href="https://github.com/Ezazulmahi/climate-risk-bd"
                className="hover:text-ink"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
            </div>
            <div className="ml-auto md:ml-0">
              <LangToggle current={lang} label={t.langSwitch} />
            </div>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t border-line px-4 py-6 text-center text-xs text-muted">
          {t.footer}{" "}
          <a className="underline" href="https://live6.bmd.gov.bd/" target="_blank" rel="noreferrer">
            {t.bmd}
          </a>
          .{" "}
          <a className="underline" href="/alerts.rss">
            RSS
          </a>
        </footer>
      </body>
    </html>
  );
}
