import { getRaw } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const month = new URL(request.url).searchParams.get("month") ?? undefined;
  const res = await getRaw("/export/districts.csv", { month });
  return new Response(res.body, {
    status: res.status,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": res.headers.get("Content-Disposition") ?? "attachment",
    },
  });
}
