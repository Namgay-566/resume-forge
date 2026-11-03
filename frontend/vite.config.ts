import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The resume template CSS lives with the backend PDF renderer; the live preview imports the
// same files so it matches the exported PDF exactly.
const resumeTemplates = path.resolve(import.meta.dirname, '../backend/app/services/export/templates/css')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
      '@resume-templates': resumeTemplates,
    },
  },
  server: {
    fs: { allow: [import.meta.dirname, resumeTemplates] },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
})
