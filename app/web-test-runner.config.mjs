import { esbuildPlugin } from '@web/dev-server-esbuild';
import { playwrightLauncher } from '@web/test-runner-playwright';

export default {
  files: 'test/**/*.test.ts',
  nodeResolve: true,
  plugins: [esbuildPlugin({ ts: true, target: 'es2020', tsconfig: './tsconfig.json' })],
  browsers: [playwrightLauncher({ product: 'chromium' })],
  filterBrowserLogs: ({ args }) => !String(args[0]).includes('Lit is in dev mode'),
  testFramework: { config: { timeout: 5000 } },
};
