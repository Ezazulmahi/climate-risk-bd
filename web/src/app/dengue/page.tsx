import type { Metadata } from "next";
import DengueChart from "@/components/DengueChart";
import { Card, ErrorPanel } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cityName, getDict, num, pctL, signedPctL } from "@/lib/i18n";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Dengue" };

export default async function DenguePage() {
  const { lang, t } = await getDict();
  let res;
  try {
    res = await api.dengue();
  } catch (e) {
    return <ErrorPanel message={e instanceof ApiError ? e.message : String(e)} />;
  }
  const bn = lang === "bn";
  const names = {
    persistence: bn ? "আগের মাসের সমান ধরা" : "Same as this month (persistence)",
    seasonal_ratio: bn ? "মৌসুমি বৃদ্ধির হার" : "Seasonal growth ratio",
    ridge: bn ? "রিজ রিগ্রেশন + আবহাওয়া" : "Ridge regression + weather",
  } as const;
  const keys = Object.keys(names) as (keyof typeof names)[];
  const best = keys.reduce((a, b) => (res.scores[a].mae_log <= res.scores[b].mae_log ? a : b));
  const cities = [...new Set(res.series.map((s) => s.city))];
  const cityLabels: Record<string, string> = Object.fromEntries(
    cities.map((c) => [c, cityName(c, lang)]),
  );
  cityLabels.__division = bn ? "বিভাগ" : "Division";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{t.dengueTitle}</h1>
        <p className="mt-2 max-w-3xl text-ink-2">{t.dengueIntro}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="font-semibold">
            {bn ? "পরীক্ষার বছরে এক মাস আগের পূর্বাভাস" : "One-month-ahead forecasts in the test years"}
          </h2>
          <div className="mt-3">
            <DengueChart
              series={res.series}
              cities={cities}
              cityLabels={cityLabels}
              labels={{
                observed: t.observed,
                persistence: names.persistence,
                seasonal: names.seasonal_ratio,
                ridge: names.ridge,
                cases: bn ? "জন" : "cases",
              }}
            />
          </div>
        </Card>
        <Card>
          <h2 className="font-semibold">{t.dengueBest}</h2>
          <div className="mt-2 text-xl font-semibold">{names[best]}</div>
          <p className="mt-1 text-sm text-ink-2">
            {bn
              ? "আবহাওয়ার তথ্য যোগ করলে মৌসুমি ধরনের চেয়ে ভালো হয়নি; মাত্র ছয় মৌসুমের ডেটা।"
              : "Adding weather did not beat the seasonal pattern on six seasons of data. The useful signal is where in the season you are and how fast cases are growing."}
          </p>
          <p className="mt-4 text-xs text-muted">{t.dengueLive}</p>
        </Card>
      </div>

      <Card>
        <h2 className="font-semibold">{bn ? "নির্ভুলতা" : "Accuracy"}</h2>
        <p className="mt-1 text-sm text-ink-2">
          {bn
            ? `পরীক্ষা: ${num(res.test_months, lang)} বিভাগ-মাস।`
            : `Test: ${res.test_months} division-months, ${res.test_period[0]} to ${res.test_period[1]}. Errors on a log scale treat a miss of 100 vs 200 cases like 10,000 vs 20,000.`}
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm tabular">
            <thead className="text-muted">
              <tr>
                <th className="py-1 pr-4 font-medium">{bn ? "পদ্ধতি" : "Method"}</th>
                <th className="py-1 pr-4 font-medium">{bn ? "ত্রুটি (লগ)" : "MAE (log cases)"}</th>
                <th className="py-1 pr-4 font-medium">{bn ? "ত্রুটি (জন)" : "MAE (cases)"}</th>
                <th className="py-1 pr-4 font-medium">
                  {bn ? "বাড়া/কমার দিক ঠিক" : "Rise/fall right"}
                </th>
                <th className="py-1 font-medium">{bn ? "দক্ষতা" : "Skill vs persistence"}</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => {
                const s = res.scores[k];
                return (
                  <tr key={k} className="border-t border-line">
                    <td className="py-1 pr-4">{names[k]}</td>
                    <td className="py-1 pr-4">{num(s.mae_log, lang, 3)}</td>
                    <td className="py-1 pr-4">{num(s.mae_cases, lang)}</td>
                    <td className="py-1 pr-4">
                      {s.direction_accuracy == null ? "—" : pctL(s.direction_accuracy, lang)}
                    </td>
                    <td className="py-1">
                      {signedPctL(s.skill_vs_persistence_log ?? 0, lang)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">
          {bn ? "ডেটা:" : "Data:"} {res.source}.{" "}
          {bn
            ? "রোগীর সংখ্যা পরীক্ষা ও রিপোর্টিংয়ের উপরও নির্ভর করে।"
            : "Case counts also depend on testing and reporting, not only transmission."}
        </p>
      </Card>
    </div>
  );
}
