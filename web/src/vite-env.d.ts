/// <reference types="vite/client" />
declare const __TILES_URL__: string;

interface ImportMetaEnv {
  readonly VITE_FEATURES_OFF?: string;
  readonly VITE_FEATURES_ON?: string;
  /** Base URL of the feedback worker, e.g. https://api.isometric.lu (comments feature). */
  readonly VITE_FEEDBACK_API?: string;
  /** Turnstile site key for the comments card. */
  readonly VITE_TURNSTILE_SITEKEY?: string;
}
