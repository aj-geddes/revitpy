import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    // The real `vscode` module only exists inside the extension host.
    alias: { vscode: fileURLToPath(new URL('./test/mocks/vscode.ts', import.meta.url)) },
  },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    testTimeout: 10000,
  },
});
