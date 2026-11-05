import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { authenticatedSuite } from "./session-fixture";

// Reuse a real saved render and its owning session. Only the new POST is
// intercepted; this test verifies interaction/payload, not model quality.
const live = process.env.VASTRAVIEW_CONTINUATION_LIVE === "1";
authenticatedSuite(test, live ? ".runtime/system-audit-20261104-session.json" : undefined);
const root = path.resolve("../experiments/striped-fidelity-20261105");
const saved = live ? JSON.parse(readFileSync(path.join(root, "baseline/cases/hm-half-hand-shirt-1/female/trial.json"), "utf8")) : null;

test("continue an owned render with one complementary garment, preserve selection on failure", async ({ page }) => {
  test.skip(!live, "Explicit opt-in required for the owning private session and saved GPU evidence.");
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/api/tryon/availability", route => route.fulfill({ json: { available: true } }));
  let body: FormData | undefined;
  await page.route("**/api/tryon/apply", async route => {
    body = await new Response(new Uint8Array(route.request().postDataBuffer()!), {
      headers: { "Content-Type": route.request().headers()["content-type"] },
    }).formData();
    await route.fulfill({ status: 503, json: { detail: "Controlled worker interruption" } });
  });
  await page.goto(`/tryon?job=${saved.jobId}`);
  await expect(page.getByTestId("viewer")).toHaveAttribute("data-loaded", "true");
  await page.getByRole("button", { name: "Add another garment" }).click();
  await expect(page.getByLabel("Garment category", { exact: true })).toHaveValue("trouser");
  await expect(page.getByLabel("Garment category", { exact: true }).locator("option[value=shirt]")).toHaveCount(0);
  await page.getByLabel("Your garment", { exact: true }).setInputFiles(path.resolve("../assets/garments/formal-pant1_hm.jpg"));
  await page.getByRole("button", { name: "Generate try-on", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Controlled worker interruption");
  expect(body!.get("sourceRunId")).toBe(saved.runId);
  expect(body!.get("garmentCategory")).toBe("trouser");
  expect(body!.get("garmentImage")).toBeTruthy();
  expect(body!.get("personImage")).toBeNull();
  expect(body!.get("topwearImage")).toBeNull();
  await expect(page.getByAltText("Selected garment conditioning image")).toBeVisible();
  await expect(page.getByText("Adding to your saved look.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Start a new look", exact: true }).click();
  await expect(page.getByLabel("Garment category", { exact: true }).locator("option[value=shirt]")).toHaveCount(1);
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
