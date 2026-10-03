/**
 * Guards against out-of-order async responses — e.g. two quick successive
 * "Analisar" clicks with different target values, where the second request's
 * response can resolve before the first's. Each call to `start()` issues a new
 * token and invalidates every token issued by an earlier `start()`, so a caller
 * applies a response's state only when `isCurrent(token)` is still true by the
 * time that response arrives.
 */
export interface RequestGuard {
  start(): number;
  isCurrent(token: number): boolean;
}

export function createRequestGuard(): RequestGuard {
  let latest = 0;
  return {
    start() {
      latest += 1;
      return latest;
    },
    isCurrent(token: number) {
      return token === latest;
    },
  };
}
