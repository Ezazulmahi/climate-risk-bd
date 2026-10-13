import type { Metadata } from "next";
import InsuranceSimulator from "@/components/InsuranceSimulator";
import { Card, ErrorPanel } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { getDict } from "@/lib/i18n";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Insurance simulator" };

export default async function InsurancePage() {
  const { lang, t } = await getDict();
  let districts: string[];
  try {
    districts = (await api.districts()).districts.map((d) => d.district).sort();
  } catch (e) {
    return <ErrorPanel message={e instanceof ApiError ? e.message : String(e)} />;
  }
  const bn = lang === "bn";
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{t.insuranceTitle}</h1>
        <p className="mt-2 max-w-3xl text-ink-2">{t.insuranceIntro}</p>
      </div>
      <Card>
        <InsuranceSimulator
          districts={districts}
          locale={bn ? "bn-BD" : "en-GB"}
          labels={{
            district: t.district,
            season: bn ? "ফসলের মৌসুম" : "Crop season",
            seasons: bn
              ? { aman: "আমন (জুল–সেপ্টে)", aus: "আউশ (মার্চ–মে)", boro: "বোরো (জানু–মার্চ)" }
              : { aman: "Aman rice (Jul–Sep)", aus: "Aus rice (Mar–May)", boro: "Boro rice (Jan–Mar)" },
            trigger: bn ? "টাকা শুরু: SPI-3 ≤" : "Starts paying at SPI-3 ≤",
            exit: bn ? "পুরো টাকা: SPI-3 ≤" : "Pays in full at SPI-3 ≤",
            sum: bn ? "বিমার পরিমাণ (৳)" : "Sum insured (৳)",
            yearsPaid: bn ? "যে বছর টাকা পেত" : "Years with a payout",
            frequency: bn ? "কত বছরে একবার" : "Roughly once every (years)",
            premium: bn ? "গড় বার্ষিক টাকা" : "Average annual payout",
            premiumNote: bn ? "ন্যায্য প্রিমিয়ামের ভিত্তি" : "the fair premium before costs",
            worst: bn ? "সবচেয়ে বড় টাকা" : "Largest payout",
            basis: bn
              ? "সতর্কতা: সূচক ও একজন কৃষকের প্রকৃত ক্ষতি সবসময় মেলে না (বেসিস রিস্ক)। সেচ থাকলে বৃষ্টি কম হলেও ফসল ভালো হতে পারে। শিক্ষামূলক উদাহরণ, কোনো বিমা পণ্য নয়।"
              : "Caveat: an index never matches one farmer's actual loss (basis risk). Irrigated fields can do fine in a dry season, and a flood can ruin a crop in a wet one. An educational example, not an insurance product.",
            loading: bn ? "লোড হচ্ছে" : "Loading",
            payout: bn ? "টাকা" : "Payout",
            none: bn ? "কোনোটি নয়" : "None",
          }}
        />
      </Card>
      <Card>
        <h2 className="font-semibold">{bn ? "কীভাবে কাজ করে" : "How it works"}</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">
          {(bn
            ? [
                "প্রতি বছর মৌসুমের শেষ মাসে জেলার ৩ মাসের খরা সূচক (SPI-3, CHIRPS বৃষ্টি থেকে) পড়া হয়।",
                "সূচক 'শুরু' সীমার নিচে নামলে টাকা দেওয়া শুরু হয়, 'পুরো' সীমায় পৌঁছালে সম্পূর্ণ টাকা; মাঝে সমানুপাতিক।",
                "গড় বার্ষিক টাকা হলো খরচ ছাড়া ন্যায্য প্রিমিয়াম। প্রকৃত প্রিমিয়ামে প্রশাসনিক খরচ ও ঝুঁকির মার্জিন যোগ হয়।",
              ]
            : [
                "Each year, the district's 3-month drought index (SPI-3, from CHIRPS rainfall) is read at the end of the crop's critical window.",
                "Below the start threshold the policy begins to pay; at the full threshold it pays everything; in between it pays proportionally.",
                "The average annual payout is the 'pure' premium. Real premiums add administration costs and a risk margin.",
              ]
          ).map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
