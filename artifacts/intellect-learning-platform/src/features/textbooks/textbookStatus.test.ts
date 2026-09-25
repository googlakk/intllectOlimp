import { describe, expect, it } from 'vitest';
import { textbookStatusView } from './textbookStatus';

describe('textbookStatusView', () => {
  it('объясняет, что нужно для сканов, и даёт перезапуск', () => {
    const view = textbookStatusView({ status: 'needs_ai', stalled: false, progress: { scans_left: 255 } });
    expect(view.label).toContain('255');
    expect(view.canRun).toBe(true);
  });

  it('во время обработки перезапуск закрыт, а застрявшую можно запустить снова', () => {
    expect(textbookStatusView({ status: 'recognizing', stalled: false, progress: { scans_left: 12 } }).canRun).toBe(false);
    expect(textbookStatusView({ status: 'recognizing', stalled: true, progress: {} }).canRun).toBe(true);
  });
});

describe('isTextbookRunning', () => {
  it('после запуска книга сразу «в работе», застрявшая — нет', async () => {
    const { isTextbookRunning } = await import('@/lib/api/textbooks');
    expect(isTextbookRunning({ status: 'extracting', stalled: false })).toBe(true);
    expect(isTextbookRunning({ status: 'extracting', stalled: true })).toBe(false);
    expect(isTextbookRunning({ status: 'needs_ai', stalled: false })).toBe(false);
  });
});
