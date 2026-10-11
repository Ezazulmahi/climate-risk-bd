import Link from "next/link";
import { Card } from "@/components/ui";

export default function NotFound() {
  return (
    <Card>
      <h1 className="text-xl font-semibold">Not found</h1>
      <p className="mt-2 text-ink-2">That division isn&apos;t in the forecast.</p>
      <Link href="/" className="mt-3 inline-block text-accent underline">
        Back to the outlook
      </Link>
    </Card>
  );
}
