// Bundles the extension into a single out/extension.js.
import * as esbuild from 'esbuild';

const production = process.argv.includes('--production');
const watch = process.argv.includes('--watch');

const options = {
  entryPoints: ['src/extension.ts'],
  bundle: true,
  outfile: 'out/extension.js',
  platform: 'node',
  target: 'node20',
  format: 'cjs',
  // `vscode` is provided by the extension host. bufferutil / utf-8-validate
  // are optional native accelerators that `ws` loads inside try/catch.
  external: ['vscode', 'bufferutil', 'utf-8-validate'],
  sourcemap: !production,
  minify: production,
  logLevel: 'info',
};

if (watch) {
  const context = await esbuild.context(options);
  await context.watch();
} else {
  await esbuild.build(options);
}
