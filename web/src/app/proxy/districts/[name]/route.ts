import { getRaw } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Lets browser-side tools (the insurance simulator) read a district's history
 *  without exposing the API address. */
export async function GET(_request: Request, ctx: RouteContext<"/proxy/districts/[name]">) {
  const { name } = await ctx.params;
  const res = await getRaw(`/districts/${encodeURIComponent(name)}`);
  return new Response(res.body, {
    status: res.status,
    headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=3600" },
  });
}
