import { useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import {
  metricLabels,
  type Measurements,
  type Metric,
  type Extraction,
} from "../../types/studio";
export const validMeasurements = (values?: Measurements) =>
  !!values &&
  (Object.keys(metricLabels) as Metric[]).every((key) => {
    const value = values[key];
    return (
      Number.isFinite(value) &&
      value > 0 &&
      value <=
        (key === "shoulder_width" ? 100 : key === "inseam_length" ? 200 : 400)
    );
  });
export default function MeasurementGrid({
  values,
  onChange,
  onConfirm,
  quality,
  reviewed = [],
  manualMetrics = [],
  confirmedMetrics = [],
}: {
  values?: Measurements;
  onChange: (values: Measurements, changed: Metric) => void;
  onConfirm?: (key: Metric) => void;
  quality?: Extraction["quality"];
  reviewed?: Metric[];
  manualMetrics?: Metric[];
  confirmedMetrics?: Metric[];
}) {
  const { user } = useAuth();
  const [unit, setUnit] = useState<"cm" | "in">(user?.measurement_unit ?? "cm");
  const factor = unit === "in" ? 2.54 : 1;
  const [edit, setEdit] = useState<Metric | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  return (
    <>
      <label className="field measurement-unit">
        Display measurements in
        <select
          value={unit}
          onChange={(e) => {
            setUnit(e.target.value as "cm" | "in");
            setEdit(null);
          }}
        >
          <option value="cm">Centimetres</option>
          <option value="in">Inches</option>
        </select>
      </label>
      <div className="metric-grid">
        {(Object.keys(metricLabels) as Metric[]).map((key, index) => (
          <article className="metric-card" key={key}>
            <div className="row-between">
              <span className="metric-index">M{index + 1}</span>
              {values && (
                <div className="metric-actions">
                  {quality?.metrics?.[key]?.requires_manual_review &&
                    !reviewed.includes(key) &&
                    values[key] > 0 &&
                    onConfirm && (
                      <button
                        type="button"
                        className="text-button confirm-btn"
                        aria-label={`Confirm ${metricLabels[key]}`}
                        onClick={() => onConfirm(key)}
                      >
                        Confirm
                      </button>
                    )}
                  <button
                    type="button"
                    className="text-button"
                    aria-label={`Edit ${metricLabels[key]}`}
                    onClick={() => {
                      setEdit(key);
                      setDraft(
                        values[key] ? (values[key] / factor).toFixed(1) : "",
                      );
                      setError("");
                    }}
                  >
                    Edit
                  </button>
                </div>
              )}
            </div>
            <span className="metric-name">{metricLabels[key]}</span>
            {edit === key && values ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const updated = { ...values, [key]: Number(draft) * factor };
                  if (
                    !draft ||
                    !Number.isFinite(updated[key]) ||
                    updated[key] <= 0 ||
                    updated[key] >
                      (key === "shoulder_width"
                        ? 100
                        : key === "inseam_length"
                          ? 200
                          : 400)
                  ) {
                    setError(
                      "Enter a positive measurement within the supported range.",
                    );
                    return;
                  }
                  onChange(updated, key);
                  setEdit(null);
                }}
              >
                <div className="metric-edit">
                  <input
                    autoFocus
                    type="number"
                    step=".1"
                    aria-label={`${metricLabels[key]} in ${unit === "cm" ? "centimeters" : "inches"}`}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                  <button className="text-button">Save</button>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => setEdit(null)}
                  >
                    Cancel
                  </button>
                </div>
                {error && (
                  <small role="alert" className="field-error">
                    {error}
                  </small>
                )}
              </form>
            ) : (
              <div
                className={`metric-value ${values && !values[key] ? "metric-unavailable" : ""}`}
              >
                {values?.[key]
                  ? (values[key] / factor).toFixed(1)
                  : values
                    ? "Unavailable"
                    : "—"}
                {!!values?.[key] && <small>{unit}</small>}
              </div>
            )}
            <span className="metric-caption">
              {manualMetrics.includes(key) ||
              (reviewed.includes(key) && !confirmedMetrics.includes(key))
                ? "Manually corrected"
                : confirmedMetrics.includes(key)
                  ? "Confirmed estimate"
                  : (quality?.metrics?.[key]?.message ??
                    (values
                      ? "Photo estimate · accuracy is not calibrated"
                      : "Available after your scan"))}
            </span>
            {values && (
              <small
                className="metric-caption"
                aria-label={`${metricLabels[key]} measurement status`}
              >
                {manualMetrics.includes(key) ||
                (reviewed.includes(key) && !confirmedMetrics.includes(key))
                  ? "Manual entry · image confidence does not apply"
                  : confirmedMetrics.includes(key)
                    ? quality?.metrics?.[key]?.evidence_confidence != null
                      ? `Confirmed photo estimate · evidence score ${Math.round(quality.metrics[key]!.evidence_confidence! * 100)}/100`
                      : "Confirmed photo estimate · confidence not calibrated"
                    : values[key]
                      ? quality?.metrics?.[key]?.evidence_confidence != null
                        ? `Image estimate · evidence score ${Math.round(quality.metrics[key]!.evidence_confidence! * 100)}/100 (not accuracy)`
                        : "Image estimate · confidence not calibrated"
                      : "Unavailable · enter a tape measurement"}
              </small>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
