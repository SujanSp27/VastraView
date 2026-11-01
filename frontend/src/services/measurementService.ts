import { api, jsonBody } from "./api/client";
import type { Extraction, Measurements, SavedScan } from "../types/studio";
export const measurementService = {
  extract: (
    image: File,
    height: number,
    signal?: AbortSignal,
    gender?: "male" | "female" | null,
  ) => {
    const form = new FormData();
    form.append("image", image);
    form.append("height_cm", String(height));
    if (gender) form.append("gender", gender);
    return api<Extraction>("/api/v1/measurements/extract", {
      method: "POST",
      body: form,
      signal,
    });
  },
  save: (
    measurements: Measurements,
    height_cm: number,
    source: string,
    thumbnail_base64?: string,
    gender?: "male" | "female" | null,
  ) =>
    api<SavedScan>(
      "/api/v1/profile/scans",
      jsonBody({ measurements, height_cm, source, thumbnail_base64, gender }),
    ),
  history: (offset = 0) =>
    api<{ items: SavedScan[]; total: number }>(
      `/api/v1/profile/scans?limit=12&offset=${offset}`,
    ),
  remove: (id: string) =>
    api<void>(`/api/v1/profile/scans/${id}`, { method: "DELETE" }),
};
