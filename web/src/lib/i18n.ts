import "server-only";
import { cookies } from "next/headers";

export type Lang = "en" | "bn";

/** The visitor's language, from the `lang` cookie set by the header toggle. */
export async function getLang(): Promise<Lang> {
  const value = (await cookies()).get("lang")?.value;
  return value === "bn" ? "bn" : "en";
}

const CITY_BN: Record<string, string> = {
  Dhaka: "ঢাকা",
  Chattogram: "চট্টগ্রাম",
  Khulna: "খুলনা",
  Rajshahi: "রাজশাহী",
  Sylhet: "সিলেট",
  Barishal: "বরিশাল",
  Rangpur: "রংপুর",
  Mymensingh: "ময়মনসিংহ",
};

const en = {
  site: "Bangladesh Climate Risk",
  navOutlook: "Outlook",
  navMonitor: "Drought monitor",
  navDengue: "Dengue",
  navInsurance: "Insurance simulator",
  navModel: "Model & accuracy",
  navApi: "Data & API",
  footer:
    "Portfolio demo built on ERA5 reanalysis and CHIRPS rainfall. Not an official forecast. For decisions use the",
  bmd: "Bangladesh Meteorological Department",
  issuedWith: "Outlook issued with data through",
  outlookTitle: "rainfall and drought outlook",
  noForecast: "No forecast yet",
  outlookIntro:
    "For each division: next month's expected rainfall with an 80% range, and the chance that the 3-month rainfall ending that month is in drought territory (SPI-3 ≤ −1). The usual chance is about",
  mapTitle: "Drought risk by division",
  mapNote: "Circle size = drought probability. Click a circle for details.",
  trustTitle: "How much to trust this",
  trustIntro: "Every forecast since 2020 was stored and checked against what fell",
  cityMonths: "city-months",
  trustRain: "Rainfall amount, vs. assuming a normal month",
  errorReduction: "error reduction",
  trustRainNote:
    "Effectively no skill. One-month-ahead rainfall is hard to predict, so treat the expected amount as “about normal” and read the range.",
  trustRange: "80% range contained the actual rainfall",
  ofTheTime: "of the time",
  trustDrought: "Drought probability, vs. the usual rate",
  better: "better (Brier)",
  trustDroughtNote: "Real skill. Two of the three months are already observed when the forecast is made.",
  fullEvaluation: "Full evaluation →",
  allDivisions: "All divisions",
  expectedRain: "Expected rain",
  vsNormal: "vs normal",
  droughtChance: "Drought chance",
  usually: "usually",
  range80: "80% range",
  normal: "normal",
  barsNote: "Bars share one scale: light band = 80% range, dot = expected, grey tick = normal.",
  riskLow: "Low drought risk",
  riskElevated: "Elevated drought risk",
  riskHigh: "High drought risk",
  backAll: "← All divisions",
  forecastFor: "Forecast for",
  dataThrough: "data through",
  expectedRainfall: "Expected rainfall",
  outcomesLand: "8 in 10 outcomes should land here",
  normalForMonth: "Normal for the month",
  avg8115: "1981–2015 average",
  droughtProbability: "Drought probability",
  currentConditions: "Current conditions: SPI-3 is",
  forThreeMonths: "for the three months to",
  whyTitle: "Why this drought risk?",
  whyIntro:
    "Each bar shows how much a factor moves the probability compared with a typical value (positive = raises the risk).",
  typical: "typical",
  now: "now",
  heatTitle: "Heat-wave outlook",
  heatDays: "heat-wave days expected (≥ 36 °C)",
  heatNormal: "Normal",
  heatRecent: "Last 10 years",
  heatOff: "Outside the heat-wave season: no heat-wave days are normal this month.",
  heatNote: "ERA5 grid temperatures run cooler than city stations; read this as relative risk.",
  pastTitle: "Past forecasts vs what fell",
  insideRange: "observed months inside the 80% range",
  pastIntro:
    "Each point was forecast a month ahead using only data available at the time. The last point is the live forecast.",
  showTable: "Show as table",
  month: "Month",
  forecast: "Forecast",
  observed: "Observed",
  spiTitle: "Drought index (SPI-3), last 10 years",
  spiIntro: "Below −1 (red) means the 3-month rainfall was in roughly the driest 16% for that time of year.",
  trackTitle: "Track record for",
  trackIntro: "Test period 2020 onward,",
  months: "months",
  rainError: "Rainfall error (MAE)",
  ifNormal: "If we always said “normal”",
  rainSkill: "Rainfall skill",
  coverage: "80% range coverage",
  droughtMonths: "Drought months",
  droughtSkill: "Drought Brier skill",
  logTitle: "Forecast log",
  logIntro:
    "Each live forecast is saved the moment it is published and never edited, so this record can't be rewritten after the fact.",
  issued: "Issued",
  pending: "pending",
  inside: "inside range",
  outside: "outside range",
  downloadCsv: "Download CSV",
  monitorTitle: "Bangladesh Drought Monitor",
  monitorIntro:
    "All 64 districts, from CHIRPS satellite-and-gauge rainfall. Categories follow the US Drought Monitor's SPI breakpoints for the 3 months ending",
  viewCurrent: "Current conditions",
  viewOutlook: "Next-month outlook",
  noDrought: "No drought",
  outlookLegend: "Chance of drought next month",
  driestTitle: "Driest districts",
  district: "District",
  category: "Category",
  rainfall: "Rainfall",
  outlookAcc: "Outlook accuracy (test years)",
  outlookAccNote: "better than the usual rate (Brier skill) over",
  districtMonths: "district-months",
  dengueTitle: "Dengue: can next month's cases be forecast?",
  dengueIntro:
    "A backtest on division-level case counts (2020–2025) compiled from DGHS bulletins. Train 2020–2023, test 2024–2025.",
  dengueBest: "Best forecast",
  dengueLive:
    "Live dengue forecasts need a current case feed (DGHS publishes daily); this page shows how the methods would have done.",
  insuranceTitle: "Drought index insurance simulator",
  insuranceIntro:
    "Weather-index insurance pays out automatically when an index crosses a threshold, with no farm visits. Choose a district and a rule to see when it would have paid since 1981.",
  modelTitle: "Model & accuracy",
  apiTitle: "Data & API",
  langSwitch: "বাংলা",
};

export type Dict = typeof en;

const bn: Dict = {
  site: "বাংলাদেশ জলবায়ু ঝুঁকি",
  navOutlook: "পূর্বাভাস",
  navMonitor: "খরা মনিটর",
  navDengue: "ডেঙ্গু",
  navInsurance: "বিমা সিমুলেটর",
  navModel: "মডেল ও নির্ভুলতা",
  navApi: "ডেটা ও এপিআই",
  footer:
    "ERA5 রিঅ্যানালাইসিস ও CHIRPS বৃষ্টিপাত ডেটায় তৈরি একটি পোর্টফোলিও প্রকল্প। এটি সরকারি পূর্বাভাস নয়। সিদ্ধান্তের জন্য দেখুন",
  bmd: "বাংলাদেশ আবহাওয়া অধিদপ্তর",
  issuedWith: "পূর্বাভাসে ব্যবহৃত ডেটা:",
  outlookTitle: "বৃষ্টিপাত ও খরার পূর্বাভাস",
  noForecast: "এখনো কোনো পূর্বাভাস নেই",
  outlookIntro:
    "প্রতিটি বিভাগের জন্য: আগামী মাসের প্রত্যাশিত বৃষ্টিপাত (৮০% সম্ভাব্য সীমাসহ), এবং ওই মাসে শেষ হওয়া ৩ মাসের বৃষ্টিপাত খরার পর্যায়ে (SPI-3 ≤ −1) পড়ার সম্ভাবনা। সাধারণ সম্ভাবনা প্রায়",
  mapTitle: "বিভাগভিত্তিক খরার ঝুঁকি",
  mapNote: "বৃত্তের আকার = খরার সম্ভাবনা। বিস্তারিত দেখতে বৃত্তে ক্লিক করুন।",
  trustTitle: "এই পূর্বাভাস কতটা নির্ভরযোগ্য",
  trustIntro: "২০২০ সাল থেকে প্রতিটি পূর্বাভাস সংরক্ষণ করে প্রকৃত বৃষ্টির সঙ্গে মেলানো হয়েছে",
  cityMonths: "শহর-মাস",
  trustRain: "বৃষ্টির পরিমাণ, 'স্বাভাবিক মাস' ধরে নেওয়ার তুলনায়",
  errorReduction: "ত্রুটি কম",
  trustRainNote:
    "কার্যত কোনো দক্ষতা নেই। এক মাস আগে বৃষ্টির পরিমাণ বলা কঠিন, তাই প্রত্যাশিত পরিমাণকে 'প্রায় স্বাভাবিক' ধরে সীমাটি দেখুন।",
  trustRange: "৮০% সীমার মধ্যে প্রকৃত বৃষ্টি পড়েছে",
  ofTheTime: "সময়",
  trustDrought: "খরার সম্ভাবনা, সাধারণ হারের তুলনায়",
  better: "ভালো (ব্রায়ার)",
  trustDroughtNote: "প্রকৃত দক্ষতা আছে। পূর্বাভাসের সময় তিন মাসের দুই মাস ইতিমধ্যে জানা থাকে।",
  fullEvaluation: "পূর্ণ মূল্যায়ন →",
  allDivisions: "সব বিভাগ",
  expectedRain: "প্রত্যাশিত বৃষ্টি",
  vsNormal: "স্বাভাবিকের তুলনায়",
  droughtChance: "খরার সম্ভাবনা",
  usually: "সাধারণত",
  range80: "৮০% সীমা",
  normal: "স্বাভাবিক",
  barsNote: "সব বার একই মাপে: হালকা অংশ = ৮০% সীমা, বিন্দু = প্রত্যাশিত, ধূসর দাগ = স্বাভাবিক।",
  riskLow: "খরার ঝুঁকি কম",
  riskElevated: "খরার ঝুঁকি বেশি",
  riskHigh: "খরার ঝুঁকি উচ্চ",
  backAll: "← সব বিভাগ",
  forecastFor: "পূর্বাভাস:",
  dataThrough: "ডেটা পর্যন্ত",
  expectedRainfall: "প্রত্যাশিত বৃষ্টিপাত",
  outcomesLand: "১০ বারের ৮ বার ফল এই সীমায় পড়ার কথা",
  normalForMonth: "মাসের স্বাভাবিক",
  avg8115: "১৯৮১–২০১৫ গড়",
  droughtProbability: "খরার সম্ভাবনা",
  currentConditions: "বর্তমান অবস্থা: SPI-3 হলো",
  forThreeMonths: "তিন মাস, শেষ মাস",
  whyTitle: "খরার ঝুঁকি কেন এমন?",
  whyIntro:
    "প্রতিটি বার দেখায় একটি বিষয় সাধারণ মানের তুলনায় সম্ভাবনাকে কতটা বদলায় (ধনাত্মক = ঝুঁকি বাড়ায়)।",
  typical: "সাধারণ",
  now: "এখন",
  heatTitle: "তাপপ্রবাহের পূর্বাভাস",
  heatDays: "তাপপ্রবাহের দিন প্রত্যাশিত (≥ ৩৬ °সে)",
  heatNormal: "স্বাভাবিক",
  heatRecent: "গত ১০ বছর",
  heatOff: "তাপপ্রবাহের মৌসুম নয়: এই মাসে সাধারণত কোনো তাপপ্রবাহের দিন থাকে না।",
  heatNote: "ERA5 গ্রিডের তাপমাত্রা শহরের স্টেশনের চেয়ে কম দেখায়; এটিকে আপেক্ষিক ঝুঁকি হিসেবে পড়ুন।",
  pastTitle: "আগের পূর্বাভাস বনাম প্রকৃত বৃষ্টি",
  insideRange: "পর্যবেক্ষিত মাস ৮০% সীমার মধ্যে",
  pastIntro:
    "প্রতিটি বিন্দু এক মাস আগে, তখন পাওয়া ডেটা দিয়েই পূর্বাভাস করা। শেষ বিন্দুটি চলতি পূর্বাভাস।",
  showTable: "সারণি দেখুন",
  month: "মাস",
  forecast: "পূর্বাভাস",
  observed: "পর্যবেক্ষিত",
  spiTitle: "খরা সূচক (SPI-3), গত ১০ বছর",
  spiIntro: "−১ এর নিচে (লাল) মানে ৩ মাসের বৃষ্টি বছরের ওই সময়ের সবচেয়ে শুষ্ক প্রায় ১৬%-এর মধ্যে ছিল।",
  trackTitle: "পূর্বাভাসের রেকর্ড:",
  trackIntro: "পরীক্ষাকাল ২০২০ থেকে,",
  months: "মাস",
  rainError: "বৃষ্টির ত্রুটি (MAE)",
  ifNormal: "সবসময় 'স্বাভাবিক' বললে",
  rainSkill: "বৃষ্টির দক্ষতা",
  coverage: "৮০% সীমার কভারেজ",
  droughtMonths: "খরার মাস",
  droughtSkill: "খরার ব্রায়ার দক্ষতা",
  logTitle: "পূর্বাভাসের খাতা",
  logIntro:
    "প্রতিটি চলতি পূর্বাভাস প্রকাশের মুহূর্তে সংরক্ষিত হয় এবং আর বদলানো হয় না, তাই এই রেকর্ড পরে পাল্টানো যায় না।",
  issued: "প্রকাশিত",
  pending: "অপেক্ষমাণ",
  inside: "সীমার মধ্যে",
  outside: "সীমার বাইরে",
  downloadCsv: "CSV ডাউনলোড",
  monitorTitle: "বাংলাদেশ খরা মনিটর",
  monitorIntro:
    "৬৪টি জেলা, CHIRPS উপগ্রহ ও বৃষ্টিমাপক ডেটা থেকে। শ্রেণিগুলো যুক্তরাষ্ট্রের ড্রাউট মনিটরের SPI সীমা অনুসরণ করে; ৩ মাস শেষ:",
  viewCurrent: "বর্তমান অবস্থা",
  viewOutlook: "আগামী মাসের পূর্বাভাস",
  noDrought: "খরা নেই",
  outlookLegend: "আগামী মাসে খরার সম্ভাবনা",
  driestTitle: "সবচেয়ে শুষ্ক জেলা",
  district: "জেলা",
  category: "শ্রেণি",
  rainfall: "বৃষ্টিপাত",
  outlookAcc: "পূর্বাভাসের নির্ভুলতা (পরীক্ষার বছর)",
  outlookAccNote: "সাধারণ হারের চেয়ে ভালো (ব্রায়ার দক্ষতা), মোট",
  districtMonths: "জেলা-মাস",
  dengueTitle: "ডেঙ্গু: আগামী মাসের রোগী সংখ্যা কি অনুমান করা যায়?",
  dengueIntro:
    "বিভাগভিত্তিক রোগী সংখ্যার (২০২০–২০২৫, স্বাস্থ্য অধিদপ্তরের বুলেটিন থেকে সংকলিত) উপর পরীক্ষা। প্রশিক্ষণ ২০২০–২০২৩, পরীক্ষা ২০২৪–২০২৫।",
  dengueBest: "সেরা পদ্ধতি",
  dengueLive:
    "চলতি ডেঙ্গু পূর্বাভাসের জন্য হালনাগাদ রোগীর তথ্য দরকার (স্বাস্থ্য অধিদপ্তর প্রতিদিন প্রকাশ করে); এই পাতা দেখায় পদ্ধতিগুলো অতীতে কেমন করত।",
  insuranceTitle: "খরা সূচক বিমা সিমুলেটর",
  insuranceIntro:
    "আবহাওয়া-সূচক বিমায় কোনো সূচক নির্দিষ্ট সীমা পার হলে মাঠ পরিদর্শন ছাড়াই স্বয়ংক্রিয়ভাবে টাকা দেওয়া হয়। একটি জেলা ও নিয়ম বেছে নিয়ে দেখুন ১৯৮১ থেকে কবে টাকা পাওয়া যেত।",
  modelTitle: "মডেল ও নির্ভুলতা",
  apiTitle: "ডেটা ও এপিআই",
  langSwitch: "English",
};

export const dictionaries: Record<Lang, Dict> = { en, bn };

// Bangla labels for the forecast-explanation factors, keyed by feature name.
const DRIVER_BN: Record<string, string> = {
  precip_anom_z: "এ মাসের বৃষ্টি, স্বাভাবিকের তুলনায়",
  precip_anom_z_lag1: "গত মাসের বৃষ্টি, স্বাভাবিকের তুলনায়",
  precip_anom_z_lag2: "দুই মাস আগের বৃষ্টি, স্বাভাবিকের তুলনায়",
  precip_anom_z_lag11: "গত বছরের একই মাস, স্বাভাবিকের তুলনায়",
  precip_anom_z_roll3: "গত ৩ মাসের বৃষ্টি, স্বাভাবিকের তুলনায়",
  precip_anom_z_roll6: "গত ৬ মাসের বৃষ্টি, স্বাভাবিকের তুলনায়",
  spi1: "১ মাসের খরা সূচক",
  spi3: "৩ মাসের খরা সূচক",
  spi6: "৬ মাসের খরা সূচক",
  spi12: "১২ মাসের খরা সূচক",
  drought_prob_ens: "ইতিমধ্যে পড়া বৃষ্টি থেকে খরার সম্ভাবনা",
  t2m_anom: "তাপমাত্রা, স্বাভাবিকের তুলনায়",
  t2m_anom_roll3: "গত ৩ মাসের তাপমাত্রা, স্বাভাবিকের তুলনায়",
  rh2m_anom: "আর্দ্রতা, স্বাভাবিকের তুলনায়",
  ws10m: "বাতাসের গতি",
  target_month_sin: "বছরের সময়",
  target_month_cos: "বছরের সময়",
  clim_precip_mean_next: "আগামী মাসের স্বাভাবিক বৃষ্টি",
  lat: "অবস্থান",
  lon: "অবস্থান",
  oni: "এল নিনো / লা নিনা",
  dmi_lag4: "ভারত মহাসাগরীয় ডাইপোল",
};

export function driverLabel(label: string, features: string[], lang: Lang): string {
  return lang === "bn" ? (DRIVER_BN[features[0]] ?? label) : label;
}

export async function getDict(): Promise<{ lang: Lang; t: Dict }> {
  const lang = await getLang();
  return { lang, t: dictionaries[lang] };
}

export function cityName(name: string, lang: Lang): string {
  return lang === "bn" ? (CITY_BN[name] ?? name) : name;
}

const locale = (lang: Lang) => (lang === "bn" ? "bn-BD" : "en-GB");

export function num(v: number, lang: Lang, digits = 0): string {
  return v.toLocaleString(locale(lang), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function pctL(v: number, lang: Lang, digits = 0): string {
  return `${num(v * 100, lang, digits)}%`;
}

export function signedPctL(v: number, lang: Lang, digits = 1): string {
  return `${v >= 0 ? "+" : "−"}${num(Math.abs(v * 100), lang, digits)}%`;
}

export function mmL(v: number, lang: Lang): string {
  return `${num(Math.round(v), lang)} ${lang === "bn" ? "মিমি" : "mm"}`;
}

export function signedMmL(v: number, lang: Lang): string {
  return `${v >= 0 ? "+" : "−"}${mmL(Math.abs(v), lang)}`;
}

export function monthL(ym: string, lang: Lang, style: "long" | "short" = "long"): string {
  const [y, m] = ym.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString(locale(lang), {
    month: style,
    year: "numeric",
    timeZone: "UTC",
  });
}
