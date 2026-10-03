import { expect, test } from "@playwright/test";

const WAITLIST_SUCCESS_MESSAGE = "Você está na lista — avisaremos no lançamento.";

test.describe("landing hero intro", () => {
  test("reduced motion shows the static hero, no canvas, headline visible immediately", async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    await page.goto("/");

    // Headline is server-rendered visible and nothing in this mode ever hides it.
    await expect(page.locator("h1")).toBeVisible();

    // The static fallback's own P50 label (distinct from the 3D scene's live labels,
    // which never render while the fallback is showing).
    await expect(page.locator('.hero-stage [data-layer="static"]').getByText("P50")).toBeVisible();

    // No WebGL scene ever mounts: give it the full 3s window the brief calls for, then
    // assert zero canvases — a flaky "it just hasn't appeared *yet*" pass is not acceptable.
    await page.waitForTimeout(3000);
    await expect(page.locator(".hero-stage canvas")).toHaveCount(0);

    await context.close();
  });

  test("intro skips on interaction, well before the natural 7s reveal", async ({ page }) => {
    // Fresh context already has empty sessionStorage, but clear explicitly so the intro
    // reliably plays regardless of test order / context reuse.
    await page.addInitScript(() => window.sessionStorage.clear());
    await page.goto("/");

    const canvas = page.locator(".hero-stage canvas");
    await expect(canvas).toBeAttached({ timeout: 15000 });

    const heroCopy = page.locator("[data-intro-target]");
    // Guard against a false pass: confirm the intro is genuinely running (not already
    // settled from a prior visit) before we try to skip it.
    await expect(heroCopy).toHaveAttribute("data-intro", "playing", { timeout: 5000 });

    await page.waitForTimeout(1000); // ~1s into the 7s intro
    await page.mouse.wheel(0, 200);

    // The scene's skip listener jumps straight to the settled frame on the next RAF tick,
    // so "done" should land almost immediately — comfortably inside 2.5s, far short of 7s.
    await expect(heroCopy).toHaveAttribute("data-intro", "done", { timeout: 2500 });

    // And the live P50 label is actually visually revealed (opacity transitioned in),
    // not just present in the DOM with opacity 0.
    // exact: true — "P50" (unqualified) also appears in the static legend ("P50 · mediana")
    // and the figure's sr-only caption; only the live label's <b> text is exactly "P50".
    const liveP50 = page.locator(".hero-stage").getByText("P50", { exact: true });
    await expect(liveP50).toBeVisible();
    await expect.poll(() => liveP50.evaluate((el) => getComputedStyle(el).opacity)).toBe("1");
  });
});

test.describe("waitlist form", () => {
  test("submits from the Consultor card and shows the confirmation sentence", async ({ page }) => {
    await page.route("**/api/v1/waitlist", (route) =>
      route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ status: "ok" }) }),
    );

    await page.goto("/");

    const consultorCard = page.locator("article.plan-card").filter({ hasText: "Consultor" });
    await consultorCard.getByPlaceholder("seu@email.com").fill("investidor@example.com");
    await consultorCard.getByRole("button", { name: "Entrar na lista" }).click();

    await expect(consultorCard.getByText(WAITLIST_SUCCESS_MESSAGE)).toBeVisible();
  });
});
