import { describe, expect, it } from 'vitest';
import type { StudentTutorTurn } from '@/lib/api';
import { teacherNotes } from './StudentTutorReport';

const base: StudentTutorTurn = {
  id: 1, created_at: null, lesson_version_id: 1, block_index: 0, question_index: null, event: 'message',
  student_text: 'скажи ответ', student_value: null, check_outcome: null, reply: 'Давай по шагам', source: 'guard',
  action: null, misconception_code: null, diagnosis: null, safety_flag: 'none', off_topic: false, leak_blocked: false,
};

describe('teacherNotes', () => {
  it('показывает учителю скрытые пометки', () => {
    expect(teacherNotes({ ...base, leak_blocked: true, safety_flag: 'cheating_request', diagnosis: 'умножил вместо деления' }))
      .toEqual(['Диагноз: умножил вместо деления', 'Ответ задачи скрыт защитой', 'просил готовый ответ']);
    expect(teacherNotes({ ...base, safety_flag: 'distress', action: 'call_teacher' }))
      .toEqual(['тревожное сообщение', 'Отмечено: нужен учитель']);
    expect(teacherNotes(base)).toEqual([]);
  });
});
