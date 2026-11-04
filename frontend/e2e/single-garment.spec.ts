import { test, expect } from "@playwright/test";
import path from "node:path";
import { mkdirSync, readFileSync } from "node:fs";
import { authenticatedSuite } from "./session-fixture";

authenticatedSuite(test);

test("running API retires combined submission and rejects a second garment", async ({
  page,
}) => {
  const retired = await page.request.post("/api/tryon/outfit");
  expect(retired.status()).toBe(410);
  expect(await retired.text()).toContain("single_garment_only");
  const rejected = await page.request.post("/api/tryon", {
    multipart: {
      personImage: {
        name: "person.jpg",
        mimeType: "image/jpeg",
        buffer: readFileSync(person),
      },
      garmentImage: {
        name: "shirt.jpg",
        mimeType: "image/jpeg",
        buffer: readFileSync(shirt),
      },
      bottomwearImage: {
        name: "pants.jpg",
        mimeType: "image/jpeg",
        buffer: readFileSync(trousers),
      },
      garmentCategory: "t-shirt",
    },
  });
  expect(rejected.status()).toBe(422);
  expect(await rejected.text()).toContain("single_garment_only");
  const schema = await (
    await page.request.get("http://127.0.0.1:8000/openapi.json")
  ).json();
  expect(schema.paths["/api/tryon/outfit"]).toBeUndefined();
});
const person = path.resolve("../data/raw/studio-person.jpg");
const shirt = path.resolve("../data/raw/sage-polo.jpg");
const trousers = path.resolve("../assets/garments/formal-pant1_hm.jpg");
const preview = "Selected garment conditioning image";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/tryon/availability", (route) =>
    route.fulfill({ json: { available: true } }),
  );
  await page.route("**/api/v1/products?*", (route) =>
    route.fulfill({ json: { items: [], total: 0 } }),
  );
});

test("one garment at a time: shirt then trousers, person unchanged, exactly one request per generation", async ({
  page,
}) => {
  const bodies: FormData[] = [];
  let combined = 0;
  await page.route("**/api/tryon/outfit", (route) => {
    combined++;
    return route.fulfill({ status: 410 });
  });
  await page.route("**/api/tryon", async (route) => {
    bodies.push(
      await new Response(new Uint8Array(route.request().postDataBuffer()!), {
        headers: { "Content-Type": route.request().headers()["content-type"] },
      }).formData(),
    );
    await route.fulfill({
      status: 503,
      json: { detail: "Transport-only generation failure" },
    });
  });
  await page.goto("/tryon");
  await expect(
    page.getByRole("heading", { name: "Single Garment", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Outfit workflow")).toHaveCount(0);
  await expect(page.getByLabel("Your bottomwear", { exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("button", { name: "Browse bottomwear" }),
  ).toHaveCount(0);
  await page
    .getByLabel("Your person photo", { exact: true })
    .setInputFiles(person);
  await page.getByLabel("Your garment", { exact: true }).setInputFiles(shirt);
  await expect(page.getByAltText(preview)).toBeVisible();
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Transport-only");
  await page
    .getByLabel("Your garment", { exact: true })
    .setInputFiles(trousers);
  await page
    .getByLabel("Garment category", { exact: true })
    .selectOption("trouser");
  await expect(page.getByText("sage-polo.jpg", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText("formal-pant1_hm.jpg", { exact: true }),
  ).toBeVisible();
  mkdirSync("../experiments/single-garment-20261104", { recursive: true });
  await page.screenshot({
    path: "../experiments/single-garment-20261104/desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 375, height: 850 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../experiments/single-garment-20261104/mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Transport-only");
  expect(bodies).toHaveLength(2);
  expect(combined).toBe(0);
  expect(bodies.map((body) => body.get("garmentCategory"))).toEqual([
    "t-shirt",
    "trouser",
  ]);
  for (const body of bodies) {
    expect([...body.keys()].sort()).toEqual([
      "garmentCategory",
      "garmentImage",
      "garmentPhotoType",
      "personImage",
    ]);
    expect(body.getAll("garmentImage")).toHaveLength(1);
  }
  expect(await (bodies[0].get("personImage") as File).arrayBuffer()).toEqual(
    await (bodies[1].get("personImage") as File).arrayBuffer(),
  );
  expect((bodies[1].get("garmentImage") as File).name).toBe(
    "formal-pant1_hm.jpg",
  );
  await page
    .getByRole("button", { name: "Remove Your garment", exact: true })
    .click();
  await expect(page.getByAltText(preview)).toHaveCount(0);
  await expect(
    page.getByText("studio-person.jpg", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate try-on", exact: true }),
  ).toBeDisabled();
  for (const category of [
    "t-shirt",
    "shirt",
    "blouse",
    "sweater",
    "jacket",
    "dress",
    "trouser",
    "jeans",
    "shorts",
    "skirt",
  ]) {
    await page
      .getByLabel("Garment category", { exact: true })
      .selectOption(category);
    await expect(page.getByLabel("Your garment", { exact: true })).toHaveCount(
      1,
    );
  }
});

test("catalog replaces the sole reference and custom upload clears its product ID", async ({
  page,
}) => {
  const items = [
    {
      id: "single-shirt",
      name: "Test shirt",
      category: "shirt",
      photoType: "model",
      imageUrl: "/single/shirt.jpg",
      description: "Transport fixture",
    },
    {
      id: "single-pants",
      name: "Test trousers",
      category: "trouser",
      photoType: "flat-lay",
      imageUrl: "/single/pants.jpg",
      description: "Transport fixture",
    },
  ];
  await page.route("**/api/v1/products?*", (route) =>
    route.fulfill({ json: { items, total: 2 } }),
  );
  await page.route("**/single/*.jpg", (route) =>
    route.fulfill({
      path: route.request().url().endsWith("shirt.jpg") ? shirt : trousers,
      contentType: "image/jpeg",
    }),
  );
  const bodies: FormData[] = [];
  await page.route("**/api/tryon", async (route) => {
    bodies.push(
      await new Response(new Uint8Array(route.request().postDataBuffer()!), {
        headers: { "Content-Type": route.request().headers()["content-type"] },
      }).formData(),
    );
    await route.fulfill({
      status: 503,
      json: { detail: "Reference transport test" },
    });
  });
  await page.goto("/tryon");
  await page
    .getByLabel("Your person photo", { exact: true })
    .setInputFiles(person);
  await page.getByRole("button", { name: /Test shirt/ }).click();
  await expect(
    page.getByLabel("Garment category", { exact: true }),
  ).toHaveValue("shirt");
  await page.getByRole("button", { name: /Test trousers/ }).click();
  await expect(
    page.getByLabel("Garment category", { exact: true }),
  ).toHaveValue("trouser");
  await expect(
    page.getByLabel("Garment photo type", { exact: true }),
  ).toHaveValue("flat-lay");
  await expect(page.getByAltText(preview)).toHaveCount(1);
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Reference transport");
  expect(bodies[0].get("productId")).toBe("single-pants");
  expect(
    Buffer.from(await (bodies[0].get("garmentImage") as File).arrayBuffer()),
  ).toEqual(readFileSync(trousers));
  await page.getByLabel("Your garment", { exact: true }).setInputFiles(shirt);
  await page
    .getByLabel("Garment category", { exact: true })
    .selectOption("t-shirt");
  await page
    .getByRole("button", { name: "Generate try-on", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Reference transport");
  expect(bodies[1].get("productId")).toBeNull();
  expect(bodies[1].get("garmentCategory")).toBe("t-shirt");
  expect(await (bodies[0].get("personImage") as File).arrayBuffer()).toEqual(
    await (bodies[1].get("personImage") as File).arrayBuffer(),
  );
  await page.reload();
  await expect(page.getByAltText(preview)).toHaveCount(0);
  await expect(page.getByLabel("Your bottomwear", { exact: true })).toHaveCount(
    0,
  );
  expect(bodies).toHaveLength(2);
});

test("saved combined render remains readable without a combined workflow", async ({
  page,
}) => {
  const jobId = "00000000-0000-4000-8000-000000000789";
  const result = {
    status: "success",
    mode: "2d",
    renderingMethod: "pretrained-vton",
    runId: jobId,
    originalUrl: "/single/history.png",
    previewUrl: "/single/history.png",
    garmentCategory: "jeans",
    garmentPhotoType: "flat-lay",
    timingSeconds: 50,
    warnings: [],
    artifacts: {},
    provenance: {},
    outfit: {
      strategy: "sequential-top-then-bottom",
      topwear: { previewUrl: "/unused-top.png" },
    },
  };
  let posts = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/api\/tryon(?:\/outfit)?$/.test(request.url())
    )
      posts++;
  });
  await page.route("**/single/history.png*", (route) =>
    route.fulfill({ path: person, contentType: "image/jpeg" }),
  );
  await page.route("**/api/tryon/jobs/*", (route) =>
    route.fulfill({ json: { jobId, status: "success", result } }),
  );
  await page.goto(`/tryon?job=${jobId}`);
  await expect(page.getByTestId("viewer")).toHaveAttribute(
    "data-loaded",
    "true",
  );
  await expect(
    page.getByRole("button", { name: "Combined outfit", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Topwear only", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Change outfit", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Single Garment", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("viewer")).toHaveAttribute(
    "data-loaded",
    "true",
  );
  expect(posts).toBe(0);
});

test("single garment sizing changes charts with the category and clears the previous recommendation", async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem(
      "formfit:measurement_session",
      JSON.stringify({
        measurements: {
          shoulder_width: 44,
          chest_circumference: 96,
          waist_circumference: 80,
          hip_circumference: 98,
          thigh_circumference: 54,
          inseam_length: 78,
        },
        height: 175,
      }),
    ),
  );
  const chart = (category: string, metrics: string[]) => ({
    brand_id: "fixture",
    brand_name: "Transport fixture",
    apparel_id: category,
    category,
    version: 1,
    gender: "unisex",
    market: "IN",
    is_demo: false,
    source: "Transport fixture only",
    measurement_basis: "body",
    active_metrics: metrics,
    notes: [],
  });
  const charts = [
    chart("t-shirt", ["chest_circumference"]),
    chart("jeans", ["waist_circumference", "hip_circumference"]),
  ];
  await page.route("**/api/v1/sizing/brands?*", (route) =>
    route.fulfill({
      json: [
        {
          brand_id: "fixture",
          brand_name: "Transport fixture",
          recommendation_available: true,
          available_charts: charts,
        },
      ],
    }),
  );
  const payloads: Record<string, unknown>[] = [];
  await page.route("**/api/v1/sizing/recommend", (route) => {
    const body = route.request().postDataJSON();
    payloads.push(body);
    return route.fulfill({
      json: {
        recommended_size: body.apparel_id === "jeans" ? "30" : "M",
        chart: charts.find((chart) => chart.apparel_id === body.apparel_id),
        warnings: [],
      },
    });
  });
  await page.goto("/tryon");
  await page.getByText("Garment size recommendation", { exact: true }).click();
  await page
    .getByLabel("Garment size chart", { exact: true })
    .selectOption("fixture/t-shirt/1");
  await page
    .getByRole("button", { name: "Find garment size", exact: true })
    .click();
  await expect(page.getByText("Garment: M", { exact: true })).toBeVisible();
  await page
    .getByLabel("Garment category", { exact: true })
    .selectOption("jeans");
  await expect(page.getByText("Garment: M", { exact: true })).toHaveCount(0);
  await page.getByText("Garment size recommendation", { exact: true }).click();
  await page
    .getByLabel("Garment size chart", { exact: true })
    .selectOption("fixture/jeans/1");
  await page
    .getByRole("button", { name: "Find garment size", exact: true })
    .click();
  await expect(page.getByText("Garment: 30", { exact: true })).toBeVisible();
  expect(payloads[0].measurements).toEqual({ chest_circumference: 96 });
  expect(payloads[1].measurements).toEqual({
    waist_circumference: 80,
    hip_circumference: 98,
  });
});
