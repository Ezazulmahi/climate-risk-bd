import type { Metadata } from "next";
import { Card } from "@/components/ui";
import { getDict } from "@/lib/i18n";

export const metadata: Metadata = { title: "Data & API" };

const ENDPOINTS: [string, string, string][] = [
  ["GET /forecasts/latest", "Live forecast for every division (rainfall, drought, heat)", "ভিত্তি পূর্বাভাস, সব বিভাগ"],
  ["GET /forecast?city=Dhaka&month=2024-08", "One stored forecast with its observed outcome", "একটি পূর্বাভাস ও প্রকৃত ফল"],
  ["GET /forecasts?city=Sylhet&start=2022-01", "A division's forecast history with outcomes", "একটি বিভাগের পূর্বাভাসের ইতিহাস"],
  ["GET /issued?city=Dhaka", "Frozen forecast log (never edited after publishing)", "অপরিবর্তনীয় পূর্বাভাসের খাতা"],
  ["GET /explain?city=Dhaka", "Top drivers of the live drought probability", "খরার সম্ভাবনার প্রধান কারণ"],
  ["GET /verification?city=Dhaka", "Skill, interval coverage, Brier score from stored forecasts", "সংরক্ষিত পূর্বাভাসের নির্ভুলতা"],
  ["GET /history?city=Dhaka&start=2020-01", "Monthly rainfall, normal, anomaly, SPI-3", "মাসিক বৃষ্টি ও খরা সূচক"],
  ["GET /districts?month=2026-08", "Drought monitor for all 64 districts", "৬৪ জেলার খরা মনিটর"],
  ["GET /districts/{name}", "One district's full monthly history", "একটি জেলার মাসিক ইতিহাস"],
  ["GET /districts/geojson", "District boundaries (geoBoundaries, CC BY 3.0 IGO)", "জেলার সীমানা"],
  ["GET /districts/evaluation", "Accuracy of the district drought outlook", "জেলা পূর্বাভাসের নির্ভুলতা"],
  ["GET /heat/evaluation", "Heat-wave outlook accuracy", "তাপপ্রবাহ পূর্বাভাসের নির্ভুলতা"],
  ["GET /dengue", "Dengue backtest and series", "ডেঙ্গু পরীক্ষা"],
  ["GET /validation", "ERA5 vs CHIRPS agreement by city", "ERA5 বনাম CHIRPS তুলনা"],
  ["GET /metrics", "Full test-set evaluation of the city model", "সম্পূর্ণ মূল্যায়ন"],
  ["GET /export/forecasts.csv", "All forecasts as CSV", "সব পূর্বাভাস CSV"],
  ["GET /export/districts.csv", "District monitor as CSV", "জেলা মনিটর CSV"],
  ["GET /alerts.rss", "Warnings feed", "সতর্কবার্তার ফিড"],
];

const SOURCES: [string, string, string][] = [
  ["ERA5 reanalysis (ECMWF) via Open-Meteo", "https://open-meteo.com/en/docs/historical-weather-api", "City rainfall, temperature, humidity, wind, 1981 onward"],
  ["CHIRPS v2.0 (UCSB Climate Hazards Center) via IRI Data Library", "https://www.chc.ucsb.edu/data/chirps", "District rainfall (satellite + gauges), 0.05°"],
  ["geoBoundaries ADM2 (BBS / OCHA)", "https://www.geoboundaries.org", "64 district boundaries, CC BY 3.0 IGO"],
  ["NOAA CPC Oceanic Niño Index", "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", "ENSO"],
  ["NOAA PSL Dipole Mode Index (HadISST)", "https://psl.noaa.gov/gcos_wgsp/Timeseries/DMI/", "Indian Ocean Dipole"],
  ["Hasan et al., Mendeley Data (CC BY 4.0)", "https://doi.org/10.17632/cgwjshkx5k.2", "Dengue cases by division, 2020–2025, from DGHS bulletins"],
];

export default async function DataPage() {
  const { lang, t } = await getDict();
  const bn = lang === "bn";
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{t.apiTitle}</h1>
        <p className="mt-2 max-w-3xl text-ink-2">
          {bn
            ? "সব ডেটা খোলা। নিচের লিংক থেকে CSV নামান, RSS-এ সতর্কবার্তা পান, অথবা সরাসরি এপিআই ব্যবহার করুন।"
            : "Everything here is open. Download CSVs, subscribe to alerts, or call the read-only JSON API directly."}
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <h2 className="font-semibold">{bn ? "ডাউনলোড" : "Downloads"}</h2>
          <ul className="mt-2 space-y-1 text-sm">
            <li><a className="text-accent underline" href="/download/forecasts.csv">{bn ? "সব পূর্বাভাস (CSV)" : "All forecasts with outcomes (CSV)"}</a></li>
            <li><a className="text-accent underline" href="/download/districts.csv">{bn ? "৬৪ জেলার মাসিক খরা ডেটা (CSV)" : "64-district drought monitor, all months (CSV)"}</a></li>
          </ul>
        </Card>
        <Card>
          <h2 className="font-semibold">{bn ? "সতর্কবার্তা" : "Alerts"}</h2>
          <p className="mt-2 text-sm text-ink-2">
            {bn
              ? "উচ্চ খরা ঝুঁকি, তাপপ্রবাহ ও তীব্র খরায় থাকা জেলার খবর যেকোনো RSS রিডারে পান।"
              : "High drought risk, heat-wave outlooks and districts in severe drought, in any feed reader."}
          </p>
          <a className="mt-2 inline-block text-sm text-accent underline" href="/alerts.rss">/alerts.rss</a>
        </Card>
        <Card>
          <h2 className="font-semibold">{bn ? "কোড" : "Code"}</h2>
          <p className="mt-2 text-sm text-ink-2">
            {bn ? "পাইথন পাইপলাইন, এপিআই ও ওয়েবসাইট — সব ওপেন সোর্স।" : "Python pipeline, FastAPI backend and this Next.js site are open source (MIT)."}
          </p>
          <a className="mt-2 inline-block text-sm text-accent underline" href="https://github.com/Ezazulmahi/climate-risk-bd" target="_blank" rel="noreferrer">GitHub →</a>
        </Card>
      </div>

      <Card>
        <h2 className="font-semibold">{bn ? "এপিআই (শুধু পড়ার জন্য, JSON)" : "API (read-only JSON)"}</h2>
        <p className="mt-1 text-sm text-ink-2">
          {bn
            ? "এপিআই সার্ভারের /docs পাতায় ইন্টারঅ্যাকটিভ ডকুমেন্টেশন আছে।"
            : "The API server serves interactive documentation at /docs (FastAPI / OpenAPI)."}
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <tbody>
              {ENDPOINTS.map(([path, en, bnText]) => (
                <tr key={path} className="border-t border-line">
                  <td className="py-1.5 pr-4 font-mono text-xs">{path}</td>
                  <td className="py-1.5 text-ink-2">{bn ? bnText : en}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="font-semibold">{bn ? "ডেটার উৎস" : "Data sources"}</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {SOURCES.map(([name, url, use]) => (
            <li key={name}>
              <a className="text-accent underline" href={url} target="_blank" rel="noreferrer">{name}</a>
              <span className="text-ink-2"> · {use}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted">
          {bn
            ? "NASA POWER-এর বৃষ্টির ডেটা বাংলাদেশে সময়ের সঙ্গে অসামঞ্জস্যপূর্ণ বলে বাদ দেওয়া হয়েছে।"
            : "NASA POWER rainfall was evaluated and rejected: its Bangladesh series changes level over time (see the model page)."}
        </p>
      </Card>
    </div>
  );
}
