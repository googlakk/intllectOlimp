import { describe, expect, it, vi } from 'vitest';
import { credentialsCsv, runCredentialBatches } from './credentialBatch';

describe('class credential operations', () => {
  it('sends small sequential batches with accurate progress and row offsets', async () => {
    const send = vi.fn(async (batch: number[]) => batch);
    const receive = vi.fn();
    await runCredentialBatches([1, 2, 3, 4, 5, 6, 7], send, receive);
    expect(send.mock.calls).toEqual([[[1, 2, 3], 0], [[4, 5, 6], 3], [[7], 6]]);
    expect(receive.mock.calls).toEqual([[[1, 2, 3], 3, 0], [[4, 5, 6], 6, 3], [[7], 7, 6]]);
  });
  it('preserves issued results and never retries or sends later batches after a lost response', async () => {
    const receive = vi.fn();
    const send = vi.fn().mockResolvedValueOnce(['issued']).mockRejectedValueOnce(new Error('Connection lost'));
    await expect(runCredentialBatches([1, 2, 3, 4, 5, 6, 7], send, receive)).rejects.toThrow('Connection lost');
    expect(receive).toHaveBeenCalledExactlyOnceWith(['issued'], 3, 0);
    expect(send).toHaveBeenCalledTimes(2);
  });
  it('exports student names and quoted credentials without spreadsheet formulas', () => {
    const csv = credentialsCsv([{ display_name: '=HYPERLINK("bad")', login: 'student.7a', temporary_password: '+123456' }]);
    expect(csv).toContain('"\'=HYPERLINK(""bad"")";"student.7a";"\'+123456"');
    expect(csv.startsWith('\uFEFF')).toBe(true);
  });
});
