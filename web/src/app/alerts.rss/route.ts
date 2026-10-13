import { getRaw } from "@/lib/api";

export const dynamic = "force-dynamic";

/** The API's alerts feed, served from the site's own domain for feed readers. */
export async function GET() {
  const res = await getRaw("/alerts.rss");
  return new Response(res.body, {
    status: res.status,
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
}
