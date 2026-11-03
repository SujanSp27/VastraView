import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { sizingService } from "../../services/sizingService";
import type { Brand, Recommendation } from "../../types/studio";
import { useMeasurement } from "../measurement/MeasurementProvider";

// Separate component instances keep topwear and bottomwear chart/results independent.
export default function OutfitSizing({
  category,
  label,
}: {
  category: string;
  label: string;
}) {
  const active = useMeasurement();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState<Recommendation>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const version = useRef(0);
  const charts = brands
    .flatMap((brand) => brand.available_charts)
    .filter(
      (chart) =>
        chart.category === category &&
        chart.measurement_basis !== "garment" &&
        !chart.is_demo,
    );
  const key = (chart: (typeof charts)[number]) =>
    `${chart.brand_id}/${chart.apparel_id}/${chart.version}`;
  const chart = charts.find((item) => key(item) === selected);
  useEffect(() => {
    let current = true;
    sizingService
      .brands()
      .then((data) => {
        if (current) setBrands(data);
      })
      .catch(() => {
        if (current)
          setError("Size charts could not load. Use Find your fit to retry.");
      });
    return () => {
      current = false;
    };
  }, []);
  useEffect(() => {
    version.current++;
    setResult(undefined);
    setBusy(false);
    return () => {
      version.current++;
    };
  }, [active.measurements, active.extraction, selected]);
  async function recommend() {
    if (!chart || !active.measurements) return;
    setBusy(true);
    setError("");
    const requestVersion = version.current;
    try {
      const recommendation = await sizingService.recommend(
        chart,
        active.measurements,
        active.extraction,
        active.reviewedMetrics,
      );
      if (requestVersion === version.current) setResult(recommendation);
    } catch (e) {
      if (requestVersion === version.current) setError((e as Error).message);
    } finally {
      if (requestVersion === version.current) setBusy(false);
    }
  }
  return (
    <details className="outfit-sizing">
      <summary>{label} size recommendation</summary>
      <p className="fine-print">
        Chart-based sizing is separate from the rendered outfit. Choose the
        garment's brand, audience and region.
      </p>
      <label className="field">
        {label} size chart
        <select
          aria-label={`${label} size chart`}
          value={selected}
          disabled={busy}
          onChange={(e) => setSelected(e.target.value)}
        >
          <option value="">Select a supported chart</option>
          {charts.map((item) => (
            <option key={key(item)} value={key(item)}>
              {item.brand_name} · {item.gender} · {item.market} ·{" "}
              {item.apparel_id}
            </option>
          ))}
        </select>
      </label>
      {!charts.length && <p>No supported chart for this category.</p>}
      {!active.measurements && (
        <Link to="/measurements">Add or review your body measurements</Link>
      )}
      <button
        className="button secondary"
        disabled={busy || !chart || !active.measurements}
        onClick={() => void recommend()}
      >
        {busy ? "Checking size…" : `Find ${label.toLowerCase()} size`}
      </button>
      {error && <p role="alert">{error}</p>}
      {result && (
        <div role="status">
          <strong>
            {label}: {result.recommended_size}
          </strong>
          <p>
            {result.chart.source} ·{" "}
            {result.chart.verification_status ?? "unverified"}
          </p>
          {result.chart.source_url && (
            <a href={result.chart.source_url} target="_blank" rel="noreferrer">
              Chart source
            </a>
          )}
          {result.warnings.map((warning) => (
            <p className="fine-print" key={warning}>
              {warning}
            </p>
          ))}
        </div>
      )}
    </details>
  );
}
