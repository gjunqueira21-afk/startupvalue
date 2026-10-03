import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the landing page (Task 15). Runs against `next dev` on
 * port 3000; `reuseExistingServer` lets this reuse a dev server already
 * running locally instead of racing a second one for the port.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
