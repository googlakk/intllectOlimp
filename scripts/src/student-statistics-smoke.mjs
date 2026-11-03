/** Local-only smoke: every API response is synthetic; production data is never used. */
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';

const origin = process.env.STATISTICS_SMOKE_URL || 'http://127.0.0.1:5173';
if (!['127.0.0.1', 'localhost'].includes(new URL(origin).hostname)) throw new Error('Local test server required');
const user = { id: 1, profile_id: 1, name: 'Тестовый преподаватель', role: 'teacher', grade: null, must_change_password: false };
const summary = { completed: 1, in_progress: 1, average_score: 0, needs_practice: 1, total_published: 3, completed_published: 1, progress_percent: 33.3 };
const emptySummary = { completed: 0, in_progress: 0, average_score: null, needs_practice: 0, total_published: 1, completed_published: 0, progress_percent: 0 };
const completed = { score: 0, mastery_status: 'needs_practice', completed_at: '2026-11-01T08:00:00Z', elapsed_time_sec: 125, lesson_version_id: 7 };
const baseLesson = { topic_id: 31, name: 'Дроби и вычисления с единицами измерения', status: 'in_progress', mastery_status: 'needs_practice', score: null, completed_at: null, subject_id: 12, subject_name: 'Математика', subject_grade: 7, archived: false, published: true, historical: false, retrying: true, has_progress: true, started_at: '2026-11-03T08:00:00Z', updated_at: null, elapsed_time_sec: 45, last_completed: completed };
const report = { student_id: 50, name: 'Тестовый ученик 50', grade: 7, skills: [], summary, subjects: [
  { id: 12, name: 'Математика', grade: 7, summary: { ...summary, total_published: 2, progress_percent: 50 } },
  { id: 14, name: 'Физика', grade: 7, summary: emptySummary },
], lessons: [baseLesson, { ...baseLesson, topic_id: 32, name: 'Числовые выражения', status: 'not_started', mastery_status: 'not_assessed', has_progress: false, retrying: false, last_completed: null }, { ...baseLesson, topic_id: 40, name: 'Физические величины', subject_id: 14, subject_name: 'Физика', status: 'not_started', mastery_status: 'not_assessed', has_progress: false, retrying: false, last_completed: null }, { ...baseLesson, topic_id: 9, name: 'Архивная тема', status: 'completed', archived: true, historical: true, retrying: false, score: 0 }] };
const question = { key: '0', block_index: 0, question_index: null, component: 'IndependentProblem', stage: 'practice', prompt: 'Вычисли $2+2$ и укажи единицы измерения.', response: '4 кг', outcome: 'wrong_unit', expected: '4 м', explanation: 'Число верное, но нужно проверить единицы измерения.', attempts: 1, variant: null };
const attempt = { ...completed, status: 'in_progress', score: null, completed_at: null, version_available: true, objectives: [{ id: 'o1', text: 'Работать с единицами измерения', status: 'needs_practice', score: 0 }], questions: [question] };
let reportMode = 'normal';
const errors = [];
let page;
console.log("Launching isolated test browser");
const browser = await chromium.launch({ headless: true, channel: 'chrome', timeout: 20000 });
console.log("Browser launched");
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await context.addInitScript(({ user }) => {
    localStorage.setItem('intellect_auth_session', JSON.stringify({ access_token: 'synthetic-token', refresh_token: 'synthetic-refresh', expires_in: 3600, user }));
  }, { user });
  page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/auth/me') return json(user);
    if (path === '/api/dashboard/overview') return json({ students: 50, subjects: 2, topics: 3, published_lessons: 3, average_progress: 33.3 });
    if (path === '/api/dashboard/students') return json(Array.from({ length: 50 }, (_, index) => ({ id: index + 1, name: `Тестовый ученик ${index + 1}`, grade: 7, completed_topics: 1, average_score: 0 })));
    if (path === '/api/dashboard/students/50/learning') {
      if (reportMode === 'denied') return json({ detail: 'Ученик недоступен' }, 404);
      if (reportMode === 'error') return json({ detail: 'Test failure' }, 503);
      if (reportMode === 'empty') return json({ ...report, summary: { ...emptySummary, total_published: 0 }, subjects: [], lessons: [] });
      return json(report);
    }
    if (/\/learning\/lessons\/\d+$/.test(path)) return json({ student_id: 50, topic_id: 31, name: baseLesson.name, current: attempt, last_completed: { ...attempt, ...completed, status: 'completed', questions: [{ ...question, response: null, outcome: 'incorrect' }] } });
    if (path.endsWith('/tutor')) return json({ available: true, topics: [], alerts: [], misconceptions: [] });
    return json([]);
  });
  console.log("Opening dashboard");
  await page.goto(`${origin}/dashboard`);
  await page.getByRole('textbox', { name: 'Поиск ученика' }).fill('Тестовый');
  await page.getByRole('link', { name: 'Подробнее', exact: true }).last().waitFor();
  await page.getByRole('link', { name: 'Подробнее', exact: true }).last().scrollIntoViewIfNeeded();
  const before = await page.evaluate(() => window.scrollY);
  assert(before > 500, 'The list must be scrolled to reproduce the original problem');
  await page.getByRole('link', { name: 'Подробнее', exact: true }).last().click();
  await page.getByRole('heading', { name: report.name, exact: true }).waitFor();
  assert.equal(await page.evaluate(() => window.scrollY), 0);
  await page.getByRole('button', { name: 'Разбор заданий', exact: true }).first().click();
  await page.getByText('4 кг', { exact: true }).waitFor();
  await page.getByText('Ошибка в единицах', { exact: true }).waitFor();
  await page.getByText('Ответ не сохранялся', { exact: true }).waitFor();
  assert(new URL(page.url()).searchParams.has('topic'));
  await page.getByRole('link', { name: 'Назад к списку' }).click();
  await page.getByRole('textbox', { name: 'Поиск ученика' }).waitFor();
  console.log("List restoration", { before, after: await page.evaluate(() => window.scrollY), saved: await page.evaluate(() => sessionStorage.getItem('intellect-dashboard-list:1')) });
  await page.waitForFunction(y => Math.abs(window.scrollY - y) < 5, before);
  assert.equal(await page.getByRole('textbox', { name: 'Поиск ученика' }).inputValue(), 'Тестовый');
  await page.getByRole('link', { name: 'Подробнее', exact: true }).last().click();
  await page.getByRole('heading', { name: report.name, exact: true }).waitFor();
  await page.goBack();
  await page.getByRole('textbox', { name: 'Поиск ученика' }).waitFor();
  await page.waitForFunction(y => Math.abs(window.scrollY - y) < 5, before);
  await page.goForward();
  await page.getByRole('heading', { name: report.name, exact: true }).waitFor();
  await page.getByRole('link', { name: 'Назад к списку' }).click();
  await page.waitForFunction(y => Math.abs(window.scrollY - y) < 5, before);

  await page.goto(`${origin}/dashboard/students/50?subject=12&status=needs_practice&topic=31`);
  await page.getByText('4 кг', { exact: true }).waitFor();
  await page.locator('.katex').first().waitFor();
  await page.evaluate(() => document.fonts.ready);
  await mkdir('output/playwright', { recursive: true });
  await page.screenshot({ path: 'output/playwright/student-statistics-desktop.png', fullPage: true });
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    const size = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
    assert(size.scroll <= size.width, `Horizontal overflow at ${width}: ${size.scroll}`);
    await page.screenshot({ path: `output/playwright/student-statistics-${width}.png`, fullPage: true });
  }
  await page.reload();
  await page.getByText('4 кг', { exact: true }).waitFor();
  assert.equal(new URL(page.url()).searchParams.get('subject'), '12');
  reportMode = 'empty';
  await page.reload();
  await page.getByText('Для текущего класса пока нет доступных программ.').waitFor();
  assert((await page.getByText('Нет данных', { exact: true }).count()) > 0);
  reportMode = 'denied';
  await page.reload();
  await page.getByRole('heading', { name: 'Ученик недоступен' }).waitFor();
  reportMode = 'error';
  await page.reload();
  await page.getByRole('heading', { name: 'Не удалось загрузить статистику' }).waitFor();
  assert.equal(errors.length, 0, errors.join('\n'));
  console.log('PASS: navigation/back/search/scroll, pinned-detail UI, reload URL state, empty/denied/error, mobile 390/320, no page errors');
} catch (error) {
  await mkdir('output/playwright', { recursive: true });
  if (page) { await page.screenshot({ path: 'output/playwright/student-statistics-failure.png', fullPage: true }); console.error(await page.locator('body').innerText()); }
  throw error;
} finally { await browser.close(); }
