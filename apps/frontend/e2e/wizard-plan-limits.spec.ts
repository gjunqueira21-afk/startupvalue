import { expect, test, type Page } from "@playwright/test";

/**
 * The wizard clamps to the workspace's plan. The API is stubbed with
 * `page.route` (cross-origin to the backend URL, hence the CORS headers), so
 * this needs only the Next dev server — no backend or signed-in session.
 */
const FREE_ENTITLEMENTS = {
  plan: "free",
  max_startups: 1,
  max_scenarios_per_run: 1_000,
  white_label: false,
  full_report: false,
  target_plan_section: false,
  implied_multiples: false,
};

async function stubApi(page: Page, startups: unknown[]) {
  const cors = {
    "Access-Control-Allow-Origin": "http://localhost:3000",
    "Access-Control-Allow-Credentials": "true",
  };
  await page.route("**/api/v1/workspace/entitlements", (route) =>
    route.fulfill({ status: 200, headers: cors, contentType: "application/json", body: JSON.stringify(FREE_ENTITLEMENTS) }));
  await page.route("**/api/v1/startups", (route) =>
    route.fulfill({ status: 200, headers: cors, contentType: "application/json", body: JSON.stringify(startups) }));
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 401, headers: cors, contentType: "application/json", body: "{}" }));
}

test("free workspace: simulation counts above 1.000 are locked and the default is clamped", async ({ page }) => {
  await stubApi(page, []);
  await page.goto("/app/companies/new");

  await page.locator("#company-name").fill("Acme");
  await page.locator("#sector").fill("Serviços");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.locator("#revenue-0").fill("100000");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.locator("#metric-gross-margin").fill("60");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("button", { name: "Continuar" }).click();

  const select = page.locator("#simulation-count");
  await expect(select).toHaveValue("1000");
  await expect(select.locator('option[value="1000"]')).toBeEnabled();
  for (const locked of ["5000", "10000", "25000"]) {
    await expect(select.locator(`option[value="${locked}"]`)).toBeDisabled();
  }
  await expect(select.locator('option[value="10000"]')).toContainText("disponível no plano Empresário");
});

test("free workspace at its company cap: new-company path warns and offers the existing company", async ({ page }) => {
  await stubApi(page, [{ id: "s1", name: "Acme Existente", currency: "BRL", archived_at: null, created_at: "2026-01-01T00:00:00Z" }]);
  await page.goto("/app/companies/new");

  const warning = page.getByRole("alert").filter({ hasText: "limite de empresas" });
  await expect(warning).toBeVisible();
  await expect(warning.getByRole("link", { name: "Ver planos" })).toHaveAttribute("href", "/pricing");

  await page.locator("#company-select").selectOption("s1");
  await expect(page.locator("#company-name")).toHaveValue("Acme Existente");
  await expect(page.getByText("limite de empresas")).toHaveCount(0);
});
