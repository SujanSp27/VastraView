import { test, expect } from "@playwright/test";
import path from "node:path";
import { authenticatedSuite } from "./session-fixture";
authenticatedSuite(test);

// Transport/UI assertions only. Real GPU evaluations live in experiments/combined-outfits-*.
const topId = "00000000-0000-4000-8000-000000000123";
const top = {
  status: "success",
  mode: "2d",
  renderingMethod: "pretrained-vton",
  runId: topId,
  originalUrl: "/outfit-test/original.png",
  previewUrl: "/outfit-test/top.png",
  garmentCategory: "t-shirt",
  timingSeconds: 20,
  provenance: { backend: "FASHN VTON 1.5" },
  warnings: [],
  artifacts: {},
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/tryon/availability", (route) =>
    route.fulfill({ json: { available: true } }),
  );
  await page.route("**/api/v1/products?*", (route) =>
    route.fulfill({ json: { items: [], total: 0 } }),
  );
  await page.route("**/outfit-test/*", (route) =>
    route.fulfill({
      path: path.resolve("../data/raw/studio-person.jpg"),
      contentType: "image/jpeg",
    }),
  );
});

test("combined uploads, failed second stage, retry reuse and stage comparison", async ({
  page,
}) => {
  const requests: string[] = [];
  let current = "";
  await page.route("**/api/tryon/outfit", async (route) => {
    requests.push(route.request().postDataBuffer()!.toString("latin1"));
    current = route.request().headers()["idempotency-key"];
    await route.fulfill({ status: 202, json: { jobId: current } });
  });
  await page.route("**/api/tryon/jobs/*", (route) => {
    if (!current) return route.fulfill({ status: 404 });
    return route.fulfill({
      json:
        requests.length === 1
          ? {
              jobId: current,
              status: "failed",
              partialResult: top,
              error: {
                message: "Bottomwear failed. Your topwear result is saved.",
              },
            }
          : {
              jobId: current,
              status: "success",
              result: {
                ...top,
                runId: "00000000-0000-4000-8000-000000000456",
                previewUrl: "/outfit-test/final.png",
                garmentCategory: "jeans",
                outfit: {
                  strategy: "sequential-top-then-bottom",
                  topwear: top,
                  bottomwearCategory: "jeans",
                  topwearReused: true,
                  stageSeconds: { topwear: 0, bottomwear: 21 },
                },
              },
            },
    });
  });
  await page.goto("/tryon");
  await page
    .getByLabel("Your person photo", { exact: true })
    .setInputFiles(path.resolve("../data/raw/studio-person.jpg"));
  await page
    .getByLabel("Your garment", { exact: true })
    .setInputFiles(path.resolve("../data/raw/sage-polo.jpg"));
  await page
    .getByLabel("Your bottomwear", { exact: true })
    .setInputFiles(path.resolve("../assets/garments/formal-pant1_hm.jpg"));
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Bottomwear failed");
  expect(requests[0]).toContain('name="bottomwearImage"');
  expect(requests[0]).toContain('name="bottomwearCategory"\r\n\r\njeans');
  expect(requests[0]).not.toContain('name="topwearRunId"');
  await page.getByRole("alert").getByRole("button", { name: /retry/i }).click();
  await expect(
    page.getByRole("button", { name: "Combined outfit", exact: true }),
  ).toBeVisible();
  expect(requests[1]).toContain(`name="topwearRunId"\r\n\r\n${topId}`);
  await page.getByRole("button", { name: "Topwear only", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Topwear only", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.locator('img[src^="/outfit-test/top.png"]').first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Combined outfit", exact: true })
    .click();
  await expect(
    page.locator('img[src^="/outfit-test/final.png"]').first(),
  ).toBeVisible();
  await page.setViewportSize({ width: 375, height: 850 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("bottomwear-only uses existing single endpoint and one-piece does not combine", async ({
  page,
}) => {
  let submitted = "";
  await page.route("**/api/tryon", (route) => {
    submitted = route.request().postDataBuffer()!.toString("latin1");
    return route.fulfill({
      status: 503,
      json: { detail: "Transport test only" },
    });
  });
  await page.goto("/tryon");
  await page
    .getByLabel("Garment category", { exact: true })
    .selectOption("dress");
  await expect(page.getByLabel("Your bottomwear", { exact: true })).toHaveCount(
    0,
  );
  await page
    .getByLabel("Garment category", { exact: true })
    .selectOption("trouser");
  await page
    .getByLabel("Your person photo", { exact: true })
    .setInputFiles(path.resolve("../data/raw/studio-person.jpg"));
  await page
    .getByLabel("Your garment", { exact: true })
    .setInputFiles(path.resolve("../assets/garments/formal-pant1_hm.jpg"));
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Transport test only");
  expect(submitted).toContain('name="garmentCategory"\r\n\r\ntrouser');
  expect(submitted).not.toContain('name="bottomwearImage"');
});
