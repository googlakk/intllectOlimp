import { describe, expect, it } from 'vitest';
import { blockSourceLabel, primarySectionLabel, readLessonTextbook, studentTextbookRef } from './lessonSource';

const meta = readLessonTextbook({ textbook: { title: 'Физика. 8 класс', sections: [
  { number: '§ 12', title: 'Плотность вещества', page_from: 45, page_to: 49, role: 'primary' },
  { number: '§ 11', title: 'Масса тела', page_from: 40, page_to: 44, role: 'supporting' },
] } });

describe('lessonSource', () => {
  it('подписывает урок основным параграфом, ученику — только ссылку', () => {
    expect(primarySectionLabel(meta)).toBe('§ 12 Плотность вещества (стр. 45–49)');
    expect(studentTextbookRef(meta)).toBe('§ 12, стр. 45–49');
    expect(primarySectionLabel(readLessonTextbook({ textbook: null }))).toBeNull();
  });

  it('подписывает блоки по source_ref', () => {
    expect(blockSourceLabel({ source_ref: { kind: 'analog', item_id: 101, page: 48 } })).toBe('аналог задачи учебника, стр. 48');
    expect(blockSourceLabel({ source_ref: { kind: 'section', page: 45 } })).toBe('по параграфу, стр. 45');
    expect(blockSourceLabel({ questions: [{ source_ref: { kind: 'textbook', page: 48 } }, {}] })).toBe('по учебнику: 1 из 2 вопросов');
    expect(blockSourceLabel({ text: 'x' })).toBeNull();
  });
});
