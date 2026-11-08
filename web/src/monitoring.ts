/**
 * Error reports to Sentry, release build on isometric.lu only.
 * Errors only: no tracing, no session replay, no IP addresses, no cookies. The SDK is loaded after the map has
 * started, so it costs nothing on the first view; errors thrown before then are kept and sent once it is up.
 * DSN from .env.production (VITE_SENTRY_DSN, public by design).
 */
const DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
const ACTIVE = import.meta.env.PROD && !!DSN &&
  (!/^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || new URLSearchParams(location.search).has("sentry"));

export function startMonitoring() {
  if (!ACTIVE) return;
  const early: unknown[] = [];
  const onError = (e: ErrorEvent) => early.push(e.error ?? e.message);
  const onRejection = (e: PromiseRejectionEvent) => early.push(e.reason);
  addEventListener("error", onError);
  addEventListener("unhandledrejection", onRejection);

  const load = () => import("@sentry/browser").then((Sentry) => {
    Sentry.init({
      dsn: DSN,
      release: import.meta.env.VITE_RELEASE as string | undefined,
      environment: location.hostname === "isometric.lu" ? "production" : "preview",
      sendDefaultPii: false,
      // errors only: the default browser integrations, without tracing or replay
      tracesSampleRate: 0,
      // noise from browser extensions and from ResizeObserver, which is harmless
      denyUrls: [/^chrome-extension:\/\//, /^moz-extension:\/\//, /^safari-(web-)?extension:\/\//],
      ignoreErrors: ["ResizeObserver loop limit exceeded", "ResizeObserver loop completed with undelivered notifications"],
    });
    removeEventListener("error", onError);
    removeEventListener("unhandledrejection", onRejection);
    for (const e of early) Sentry.captureException(e);
  }).catch(() => { /* blocked by an ad blocker: nothing to do */ });

  if (document.readyState === "complete") setTimeout(load, 2000);
  else addEventListener("load", () => setTimeout(load, 2000), { once: true });
}
