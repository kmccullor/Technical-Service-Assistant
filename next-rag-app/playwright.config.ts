import { defineConfig, devices } from '@playwright/test';

const reportServer = process.env.PLAYWRIGHT_REPORT_SERVER || '';

export default defineConfig({
  testDir: './tests/performance',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'https://rni-llm-01.lab.sensus.net',
    screenshot: 'off',
    video: 'off',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  reporter: reportServer
    ? [
        ['list'],
        ['html', { outputFolder: 'playwright-report', open: 'never' }],
        ['json', { outputFile: 'playwright-report/report.json' }],
      ]
    : [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
});
