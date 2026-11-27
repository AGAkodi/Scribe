/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  /** Development only, from .env.development.local; ignored by production builds. */
  readonly VITE_DEV_ACCESS_CODE?: string
}
