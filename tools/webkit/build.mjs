// Builds a tool's page: node webkit/build.mjs <tool> [<tool> ...]
//   1. copies kit/ into <tool>/ui/kit and webshell.py into <tool>/ (every tool carries its own copy, as with look.py)
//   2. builds <tool>/ui into <tool>/ui_dist: relative paths, one plain script (a module script from a file:// page is
//      refused), loaded from disk by the tool's window (webshell.py).
// React and Vite come from Lumen's web/node_modules (tools/node_modules is a link to it).
import { build } from 'vite';
import react from '@vitejs/plugin-react';
import { cpSync, existsSync, rmSync, copyFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const tools = resolve(here, '..');

const plainScript = {
  name: 'plain-script',
  transformIndexHtml: (html) => html.replace(/<script type="module" crossorigin/g, '<script defer').replace(/ crossorigin/g, ''),
};

const names = process.argv.slice(2);
if (!names.length) {
  console.error('usage: node webkit/build.mjs <tool> [<tool> ...]');
  process.exit(2);
}
for (const name of names) {
  const tool = join(tools, name);
  const ui = join(tool, 'ui');
  if (!existsSync(join(ui, 'index.html'))) { console.error(`${name}: no ui/index.html`); process.exit(1); }
  rmSync(join(ui, 'kit'), { recursive: true, force: true });
  cpSync(join(here, 'kit'), join(ui, 'kit'), { recursive: true });
  copyFileSync(join(here, 'webshell.py'), join(tool, 'webshell.py'));
  await build({
    root: ui,
    configFile: false,
    logLevel: 'warn',
    plugins: [react(), plainScript],
    base: './',
    build: {
      outDir: join(tool, 'ui_dist'), emptyOutDir: true, assetsInlineLimit: 0, modulePreload: false, reportCompressedSize: false,
      rollupOptions: { output: { format: 'iife', inlineDynamicImports: true, entryFileNames: 'app.js', assetFileNames: '[name][extname]' } },
    },
  });
  console.log(`${name}: built ui_dist`);
}
