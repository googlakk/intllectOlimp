import { describe, expect, it } from 'vitest';

import { parseStudentCsv } from './studentCsv';

describe('parseStudentCsv', () => {
  it('skips a Russian header and accepts semicolon rows', () => {
    expect(parseStudentCsv('Имя;Логин\nАлина Осмонова;alina.7a')).toEqual([
      { display_name: 'Алина Осмонова', login: 'alina.7a' },
    ]);
  });

  it('supports quoted names with commas', () => {
    expect(parseStudentCsv('name,login\n"Иванов, Иван",ivan.7a')).toEqual([
      { display_name: 'Иванов, Иван', login: 'ivan.7a' },
    ]);
  });

  it('removes a UTF-8 byte order mark', () => {
    expect(parseStudentCsv('\uFEFFName\tUsername\nНурай\tnurai.8b')).toEqual([
      { display_name: 'Нурай', login: 'nurai.8b' },
    ]);
  });
});
