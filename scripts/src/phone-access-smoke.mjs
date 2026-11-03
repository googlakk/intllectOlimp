/** Local frontend smoke; API requests are intercepted and never reach a database. */
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, devices } from 'playwright';

const origin = process.env.PHONE_SMOKE_URL || 'http://127.0.0.1:5173';
if (!['127.0.0.1', 'localhost'].includes(new URL(origin).hostname)) throw new Error('Local test server required');
const screenshotDirectory = 'output/playwright';
await mkdir(screenshotDirectory, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const errors = [];
let currentPage;
const desktopAgent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36';

async function open(options, path = '/', signedIn = false) {
  const context = await browser.newContext(options);
  const apiRequests = [];
  await context.route(`${new URL(origin).origin}/api/**`, route => {
    apiRequests.push(new URL(route.request().url()).pathname);
    return route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"Synthetic test only"}' });
  });
  if (signedIn) await context.addInitScript(() => {
    localStorage.setItem('intellect_auth_session', JSON.stringify({ access_token: 'synthetic-token', refresh_token: 'synthetic-refresh', expires_in: 3600, user: { id: 1, profile_id: 1, name: 'Тестовый ученик', role: 'student', grade: 7 } }));
  });
  const page = await context.newPage();
  currentPage = page;
  page.setDefaultTimeout(15000);
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin + path);
  return { context, page, apiRequests };
}

async function checkPhone(options, path, screenshot) {
  const result = await open(options, path, true);
  const { page, apiRequests } = result;
  await page.getByRole('heading', { name: 'Мобильное приложение в разработке' }).waitFor();
  assert.equal(await page.locator('input[type="password"]').count(), 0);
  assert.deepEqual(apiRequests, [], 'The phone gate must prevent auth and lesson requests even with a saved session');
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'No horizontal overflow');
  const button = await page.getByRole('button', { name: 'Скопировать адрес сайта' }).boundingBox();
  assert(button.height >= 44);
  if (screenshot) await page.screenshot({ path: `${screenshotDirectory}/${screenshot}.png`, fullPage: true });
  return result;
}

try {
  console.log('Checking phone links and saved sessions');
  const phone = await checkPhone({ ...devices['iPhone 13'], permissions: ['clipboard-read', 'clipboard-write'] }, '/learn/12/31?step=2', 'phone-access-390');
  await phone.page.getByRole('button', { name: 'Скопировать адрес сайта' }).click();
  await phone.page.getByRole('button', { name: 'Адрес скопирован' }).waitFor();
  assert.equal(await phone.page.evaluate(() => navigator.clipboard.readText()), 'https://inet.edu.kg');
  await phone.page.reload();
  await phone.page.getByRole('heading', { name: 'Мобильное приложение в разработке' }).waitFor();
  await phone.page.setViewportSize({ width: 844, height: 390 });
  await phone.page.getByRole('heading', { name: 'Мобильное приложение в разработке' }).waitFor();
  assert.deepEqual(phone.apiRequests, []);
  await phone.context.close();

  console.log('Checking small phones, clipboard fallback and keyboard');
  const small = await checkPhone({ ...devices['iPhone SE'] }, '/dashboard/students/50?subject=12', 'phone-access-320');
  await small.page.evaluate(() => Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new Error('Denied')) } }));
  await small.page.getByRole('button', { name: 'Скопировать адрес сайта' }).click();
  await small.page.getByRole('status').filter({ hasText: 'вручную' }).waitFor();
  await small.page.getByLabel('Адрес сайта').focus();
  await small.page.keyboard.press('Tab');
  assert(await small.page.getByRole('button', { name: 'Скопировать адрес сайта' }).evaluate(element => element === document.activeElement));
  await small.context.close();

  console.log('Checking Android and desktop-site mode');
  for (const options of [
    devices['Pixel 7'],
    { viewport: { width: 980, height: 1200 }, screen: { width: 390, height: 844 }, userAgent: desktopAgent, hasTouch: true, isMobile: true },
  ]) {
    const result = await checkPhone(options, '/visual/density');
    await result.context.close();
  }

  console.log('Checking desktop windows and tablets');
  for (const options of [
    { viewport: { width: 1280, height: 900 } },
    { viewport: { width: 390, height: 844 }, screen: { width: 1440, height: 900 } },
    devices['iPad Mini'],
    { viewport: { width: 744, height: 1133 }, screen: { width: 744, height: 1133 }, userAgent: desktopAgent, hasTouch: true, isMobile: true },
  ]) {
    console.log('Desktop/tablet viewport:', options.viewport);
    const { context, page, apiRequests } = await open(options);
    await page.getByRole('heading', { name: 'Вход в Интеллект' }).waitFor();
    assert.equal(await page.getByRole('heading', { name: 'Мобильное приложение в разработке' }).count(), 0);
    assert.deepEqual(apiRequests, []);
    await context.close();
  }
  assert.deepEqual(errors, []);
  console.log('Phone access smoke passed: phone links, saved sessions, rotation, desktop-site mode, clipboard/fallback, keyboard, desktop and tablets.');
} catch (error) {
  console.error('Browser errors:', errors);
  if (currentPage && !currentPage.isClosed()) {
    console.error('Visible page:', await currentPage.locator('body').innerText());
    await currentPage.screenshot({ path: `${screenshotDirectory}/phone-access-failure.png`, fullPage: true });
  }
  throw error;
} finally {
  await browser.close();
}
