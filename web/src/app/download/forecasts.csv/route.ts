import { getRaw } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Proxies the API's CSV export so the API address never has to be public. */
export async function GET(request: Request) {
  const city = new URL(request.url).searchParams.get("city") ?? undefined;
  const res = await getRaw("/export/forecasts.csv", { city });
  return new Response(res.body, {
    status: res.status,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": res.headers.get("Content-Disposition") ?? "attachment",
    },
  });
}
