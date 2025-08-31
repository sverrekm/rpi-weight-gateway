import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, 'dist'),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
      output: {
        entryFileNames: 'app.js',
        assetFileNames: 'assets/[name][extname]',
        chunkFileNames: 'assets/[name].js'
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
  base: '/static/'
})
