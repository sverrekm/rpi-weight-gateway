import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// Output directory relative to the project root
const OUT_DIR = resolve(__dirname, '../../weightd/app/static')

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: OUT_DIR,
    emptyOutDir: true,  // Clean the output directory before building
    sourcemap: false,
    rollupOptions: {
      output: {
        entryFileNames: 'app.js',
        assetFileNames: '[name][extname]',
        chunkFileNames: '[name].js'
      }
    }
  },
  resolve: {
    alias: {
      '@': '/src'
    }
  },
  esbuild: {
    jsx: 'automatic'
  },
  // Ensure base path is correct for production
  base: '/static/'
})
