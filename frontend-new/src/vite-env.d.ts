/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LMS_BASE_URL?: string
  readonly VITE_LMS_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
