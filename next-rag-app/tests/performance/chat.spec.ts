import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'https://rni-llm-01.lab.sensus.net';
const API_KEY = process.env.PLAYWRIGHT_API_KEY || process.env.API_KEY || '';
const BEARER_TOKEN = process.env.PLAYWRIGHT_BEARER_TOKEN || '';

const metrics: Record<string, number[]> = {};
const errors: Record<string, string[]> = {};
function record(metric: string, value: number) {
  if (!metrics[metric]) metrics[metric] = [];
  metrics[metric].push(value);
}
function recordError(metric: string, message: string) {
  if (!errors[metric]) errors[metric] = [];
  errors[metric].push(message);
}
function percentile(values: number[], p: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(sorted.length - 1, idx))];
}

test.describe.configure({ mode: 'serial' });

test.describe('Performance smoke', () => {
  test('landing page loads (probe)', async ({ page }) => {
    const t0 = Date.now();
    try {
      const response = await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      const duration = Date.now() - t0;
      record('landing', duration);
      expect(response?.status()).toBeLessThan(500);
    } catch (error) {
      recordError('landing', String(error));
      throw error;
    }
  });

  test('chat endpoint health', async ({ request }) => {
    const t0 = Date.now();
    const response = await request.get(`${BASE_URL}/api/ollama-health`, {
      headers: API_KEY ? { 'X-API-Key': API_KEY } : {},
    });
    const duration = Date.now() - t0;
    record('chat_health', duration);
    if (!response.ok()) {
      recordError('chat_health', await response.text());
    }
    expect(response.ok()).toBeTruthy();
  });

  test('chat latency', async ({ request }) => {
    const payload = {
      conversationId: null,
      message: 'Briefly describe the Technical Service Assistant platform.',
      displayMessage: 'Briefly describe the Technical Service Assistant platform.',
    };
    const t0 = Date.now();
    const response = await request.post(`${BASE_URL}/api/chat`, {
      headers: {
        'Content-Type': 'application/json',
        ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
        ...(BEARER_TOKEN ? { Authorization: `Bearer ${BEARER_TOKEN}` } : {}),
      },
      data: JSON.stringify(payload),
      timeout: 60000,
    });
    const duration = Date.now() - t0;
    record('chat_request', duration);
    if (!response.ok()) {
      recordError('chat_request', await response.text());
    }
    expect(response.ok()).toBeTruthy();
  });

  test.afterAll(async () => {
    const landingP95 = percentile(metrics['landing'] || [], 95);
    const healthP95 = percentile(metrics['chat_health'] || [], 95);
    const chatP95 = percentile(metrics['chat_request'] || [], 95);
    console.log(`Landing P95: ${landingP95} ms`);
    console.log(`Chat health P95: ${healthP95} ms`);
    console.log(`Chat request P95: ${chatP95} ms`);
    if (Object.keys(errors).length) {
      console.warn('Performance errors encountered:', JSON.stringify(errors, null, 2));
    }
  });
});
