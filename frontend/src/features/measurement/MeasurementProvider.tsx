import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Extraction, Measurements, Metric } from "../../types/studio";

const SESSION_KEY = "formfit:measurement_session";

function loadSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

type State = {
  file: File | undefined;
  setFile: (file: File | undefined) => void;
  height: number;
  setHeight: (value: number) => void;
  extraction: Extraction | undefined;
  setExtraction: (value: Extraction | undefined) => void;
  measurements: Measurements | undefined;
  setMeasurements: (value: Measurements | undefined) => void;
  edited: boolean;
  setEdited: (value: boolean) => void;
  reviewedMetrics: Metric[];
  manualMetrics: Metric[];
  correctMeasurement: (key: Metric, value: number) => void;
  saved: boolean;
  setSaved: (value: boolean) => void;
};

const Context = createContext<State | null>(null);

export function MeasurementProvider({ children }: { children: ReactNode }) {
  const initial = loadSession();
  const [file, rawSetFile] = useState<File>();
  const [height, setHeight] = useState<number>(initial?.height ?? 172);
  const [extraction, rawSetExtraction] = useState<Extraction | undefined>(
    initial?.extraction,
  );
  const [measurements, setMeasurements] = useState<Measurements | undefined>(
    initial?.measurements,
  );
  const [edited, setEdited] = useState<boolean>(initial?.edited ?? false);
  const [manualMetrics, setManualMetrics] = useState<Metric[]>(
    initial?.manualMetrics ?? [],
  );
  const [reviewedMetrics, setReviewedMetrics] = useState<Metric[]>(
    initial?.reviewedMetrics ?? [],
  );
  const [saved, setSaved] = useState<boolean>(initial?.saved ?? false);

  useEffect(() => {
    if (measurements || extraction) {
      try {
        sessionStorage.setItem(
          SESSION_KEY,
          JSON.stringify({
            height,
            extraction,
            measurements,
            edited,
            manualMetrics,
            reviewedMetrics,
            saved,
          }),
        );
      } catch {
        // quota or private browsing limits
      }
    }
  }, [
    height,
    extraction,
    measurements,
    edited,
    manualMetrics,
    reviewedMetrics,
    saved,
  ]);

  const setExtraction = (value: Extraction | undefined) => {
    rawSetExtraction(value);
    setManualMetrics([]);
    setReviewedMetrics(
      value?.measurements
        ? (Object.keys(value.measurements) as Metric[]).filter(
            (k) => (value.measurements[k] ?? 0) > 0,
          )
        : [],
    );
    setSaved(false);
  };

  const correctMeasurement = (key: Metric, value: number) => {
    setMeasurements((previous) => ({
      shoulder_width: 0,
      chest_circumference: 0,
      waist_circumference: 0,
      hip_circumference: 0,
      thigh_circumference: 0,
      inseam_length: 0,
      ...previous,
      [key]: value,
    }));
    setManualMetrics((previous) => [...new Set([...previous, key])]);
    setReviewedMetrics((previous) => [...new Set([...previous, key])]);
    setEdited(true);
    setSaved(false);
  };

  const setFile = (value: File | undefined) => {
    rawSetFile(value);
    setExtraction(undefined);
    setMeasurements(undefined);
    setEdited(false);
    setManualMetrics([]);
    setReviewedMetrics([]);
    setSaved(false);
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch {
      // quota or private browsing limits
    }
  };

  useEffect(() => {
    const clear = () => {
      setFile(undefined);
      setHeight(172);
      try {
        sessionStorage.removeItem(SESSION_KEY);
      } catch {
        // quota or private browsing limits
      }
    };
    window.addEventListener("formfit:clear-private", clear);
    return () => window.removeEventListener("formfit:clear-private", clear);
  }, []);

  return (
    <Context.Provider
      value={{
        file,
        setFile,
        height,
        setHeight,
        extraction,
        setExtraction,
        measurements,
        setMeasurements,
        edited,
        setEdited,
        reviewedMetrics,
        manualMetrics,
        correctMeasurement,
        saved,
        setSaved,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useMeasurement() {
  const state = useContext(Context);
  if (!state) throw new Error("MeasurementProvider is missing");
  return state;
}
