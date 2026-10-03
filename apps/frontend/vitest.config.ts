import { configDefaults, defineConfig } from "vitest/config";

// Playwright owns anything under e2e/ (Task 15); without this, vitest's
// default `*.spec.ts` glob would also try to run landing.spec.ts as a unit
// test, outside a browser, against a server that may not be up.
export default defineConfig({
  test: {
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
