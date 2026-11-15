import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Built into the desktop package and loaded from disk by the window (desktop/web_chat.py): relative paths, one folder,
// and a plain script, because a module script from a file:// page is refused.
const plainScript = {
  name: 'plain-script',
  transformIndexHtml: (html) => html.replace(/<script type="module" crossorigin/g, '<script defer').replace(/ crossorigin/g, ''),
};

export default defineConfig({
  plugins: [react(), plainScript],
  base: './',
  build: {
    outDir: '../daemon/codedoctor/desktop/web_dist', emptyOutDir: true, assetsInlineLimit: 0, modulePreload: false,
    rollupOptions: { output: { format: 'iife', inlineDynamicImports: true } },
  },
});
