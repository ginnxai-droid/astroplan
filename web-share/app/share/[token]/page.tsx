import React from "react";

const SOURCE_OFFER_URL =
  process.env.ASTRO_SOURCE_OFFER_URL?.trim() ||
  "https://github.com/ginnxai-droid/astroplan";
const EPHEMERIS_LICENSE = "AGPL-3.0";

function LicenseFooter() {
  return (
    <footer style={{ marginTop: 28, fontSize: 12, color: "#555" }}>
      <p>
        Swiss Ephemeris is licensed under {EPHEMERIS_LICENSE}. The complete
        corresponding source for this service is available at{" "}
        <a href={SOURCE_OFFER_URL}>{SOURCE_OFFER_URL}</a>.
      </p>
    </footer>
  );
}

interface SharedChartPayload {
  shared_chart?: {
    chart_id: string;
    name: string;
    birth_date: string;
    birth_time: string;
    place_name: string;
    timezone_iana: string;
  };
  error?: string;
}

export default async function SharedChartPage({
  params,
}: {
  params: { token: string };
}) {
  const apiBase = process.env.ASTRO_API_URL ?? "http://localhost:8000/v1";
  let data: SharedChartPayload | null = null;
  let status = 500;

  try {
    const res = await fetch(
      `${apiBase}/share/${encodeURIComponent(params.token)}`,
      { cache: "no-store" }
    );
    status = res.status;
    data = (await res.json()) as SharedChartPayload;
  } catch {
    status = 502;
  }

  if (status !== 200 || !data?.shared_chart) {
    return (
      <main style={{ maxWidth: 680, margin: "40px auto", fontFamily: "sans-serif" }}>
        <h1>Astroplan — Share Link Unavailable</h1>
        <p>
          This shared chart link has expired, been revoked by its owner, or is invalid
          (Status {status}).
        </p>
        <LicenseFooter />
      </main>
    );
  }

  const chart = data.shared_chart;
  return (
    <main style={{ maxWidth: 680, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>Astroplan — Verifiable Chart Share (Read-Only)</h1>
      <p>Know your future, Astroplan.</p>
      <section style={{ padding: 16, border: "1px solid #ddd", borderRadius: 8 }}>
        <p><strong>Name:</strong> {chart.name}</p>
        <p><strong>Birth Date &amp; Time:</strong> {chart.birth_date} at {chart.birth_time}</p>
        <p><strong>Place:</strong> {chart.place_name} ({chart.timezone_iana})</p>
      </section>
      <p style={{ marginTop: 16, fontSize: 13, color: "#555" }}>
        Calculations are astronomically verifiable for stated settings (Sidereal Lahiri,
        Whole-Sign Houses, D9 Navamsa). Interpretations follow traditional Parashari
        Jyotish rules and are not scientifically validated.
      </p>
      <LicenseFooter />
    </main>
  );
}
