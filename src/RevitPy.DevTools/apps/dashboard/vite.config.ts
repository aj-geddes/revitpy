import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@revitpy/ui': path.resolve(__dirname, '../../packages/ui/src'),
      '@revitpy/types': path.resolve(__dirname, '../../packages/types/src'),
    },
  },
  define: {
    'process.env': {},
  },
  server: {
    port: 3000,
    host: true,
    cors: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu', 'framer-motion'],
          editor: ['@monaco-editor/react', 'monaco-editor'],
        },
      },
    },
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom'],
  },
});
