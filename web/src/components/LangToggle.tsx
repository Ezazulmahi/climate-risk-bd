"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

/** Switches between English and Bangla by setting the `lang` cookie and re-rendering. */
export default function LangToggle({ current, label }: { current: "en" | "bn"; label: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const next = current === "en" ? "bn" : "en";
  return (
    <button
      type="button"
      onClick={() => {
        document.cookie = `lang=${next}; path=/; max-age=31536000; samesite=lax`;
        start(() => router.refresh());
      }}
      disabled={pending}
      lang={next}
      className="rounded-full border border-line px-3 py-1 text-sm text-ink-2 hover:text-ink disabled:opacity-50"
      aria-label={next === "bn" ? "বাংলায় দেখুন" : "View in English"}
    >
      {label}
    </button>
  );
}
