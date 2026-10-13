import type { Metadata } from "next";
import DistrictMap from "@/components/DistrictMap";
import { Card, ErrorPanel } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { CATEGORY_COLOR } from "@/lib/colors";
import { getDict, mmL, monthL, num, pctL, signedPctL } from "@/lib/i18n";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Drought monitor" };

const CATEGORY_BN: Record<string, string> = {
  D0: "অস্বাভাবিক শুষ্ক",
  D1: "মাঝারি খরা",
  D2: "তীব্র খরা",
  D3: "চরম খরা",
  D4: "ব্যতিক্রমী খরা",
};

export default async function MonitorPage() {
  const { lang, t } = await getDict();
  let data;
  try {
    const [status, geojson, evaluation] = await Promise.all([
      api.districts(),
      api.districtGeojson(),
      api.districtEval(),
    ]);
    data = { status, geojson, evaluation };
  } catch (e) {
    return <ErrorPanel message={e instanceof ApiError ? e.message : String(e)} />;
  }
  const { status, geojson, evaluation: ev } = data;
  const catLabels = Object.fromEntries(
    status.categories
      .slice()
      .reverse()
      .map((c) => [c.code, lang === "bn" ? CATEGORY_BN[c.code] : c.label]),
  );
  const values = Object.fromEntries(
    status.districts.map((d) => [
      d.district,
      { category: d.category, prob: d.drought_prob_next, spi3: d.spi3, precip: d.precip_mm,
        normal: d.normal_mm },
    ]),
  );
  const inDrought = status.districts.filter((d) => d.category);
  const counts = Object.keys(catLabels).map(
    (code) => [code, status.districts.filter((d) => d.category === code).length] as const,
  );
  const driest = status.districts.slice(0, 12);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{t.monitorTitle}</h1>
        <p className="mt-2 max-w-3xl text-ink-2">
          {t.monitorIntro} {monthL(status.month, lang)}.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <DistrictMap
            geojson={geojson}
            values={values}
            labels={{
              current: t.viewCurrent,
              outlook: t.viewOutlook,
              noDrought: t.noDrought,
              outlookLegend: t.outlookLegend,
              rainfall: t.rainfall,
              normal: t.normal,
              chance: t.droughtChance,
              categories: catLabels,
            }}
          />
        </Card>
        <div className="space-y-6">
          <Card>
            <div className="text-3xl font-semibold tabular">
              {num(inDrought.length, lang)} / {num(status.districts.length, lang)}
            </div>
            <div className="text-sm text-ink-2">
              {lang === "bn" ? "জেলা অস্বাভাবিক শুষ্ক বা খরায়" : "districts abnormally dry or in drought"}
            </div>
            <ul className="mt-4 space-y-1 text-sm">
              {counts.map(([code, n]) => (
                <li key={code} className="flex items-center justify-between gap-3">
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="inline-block h-3 w-4 rounded-sm border border-line"
                      style={{ background: CATEGORY_COLOR[code] }}
                    />
                    {code} {catLabels[code]}
                  </span>
                  <span className="tabular">{num(n, lang)}</span>
                </li>
              ))}
            </ul>
            <a
              href={`/download/districts.csv?month=${status.month}`}
              className="mt-4 inline-block text-sm text-accent underline"
            >
              {t.downloadCsv}
            </a>
          </Card>
          <Card>
            <h2 className="font-semibold">{t.outlookAcc}</h2>
            <div className="mt-2 text-2xl font-semibold tabular">
              {signedPctL(ev.brier_skill, lang)}
            </div>
            <p className="text-sm text-ink-2">
              {t.outlookAccNote} {num(ev.n_test, lang)} {t.districtMonths}.
            </p>
            <p className="mt-2 text-xs text-muted">
              {lang === "bn"
                ? "পদ্ধতি: ইতিমধ্যে পড়া বৃষ্টি + প্রতিটি অতীত বছরের আগামী মাসের বৃষ্টি (ক্লাইমেটোলজিক্যাল এনসেম্বল)।"
                : "Method: rain already observed plus every past year's rain for the coming month (climatological ensemble), which matched machine learning in testing."}
            </p>
          </Card>
        </div>
      </div>

      <Card>
        <h2 className="font-semibold">{t.driestTitle}</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm tabular">
            <thead className="text-muted">
              <tr>
                <th className="py-1 pr-4 font-medium">{t.district}</th>
                <th className="py-1 pr-4 font-medium">{t.category}</th>
                <th className="py-1 pr-4 font-medium">SPI-3</th>
                <th className="py-1 pr-4 font-medium">{t.rainfall}</th>
                <th className="py-1 pr-4 font-medium">{t.normal}</th>
                <th className="py-1 font-medium">{t.outlookLegend}</th>
              </tr>
            </thead>
            <tbody>
              {driest.map((d) => (
                <tr key={d.district} className="border-t border-line">
                  <td className="py-1 pr-4">{d.district}</td>
                  <td className="py-1 pr-4">
                    {d.category ? `${d.category} ${catLabels[d.category]}` : t.noDrought}
                  </td>
                  <td className="py-1 pr-4">{d.spi3 == null ? "—" : num(d.spi3, lang, 2)}</td>
                  <td className="py-1 pr-4">{d.precip_mm == null ? "—" : mmL(d.precip_mm, lang)}</td>
                  <td className="py-1 pr-4">{d.normal_mm == null ? "—" : mmL(d.normal_mm, lang)}</td>
                  <td className="py-1">
                    {d.drought_prob_next == null ? "—" : pctL(d.drought_prob_next, lang)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
