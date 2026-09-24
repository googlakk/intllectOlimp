import { describe, expect, it } from 'vitest';
import { assessmentQuestions } from './assessmentModel';
describe('assessment questions', () => {
  it('retains original block and question indexes for server evidence', () => {
    const result = assessmentQuestions([
      { component: 'ShortExplanation', content: { text: 'intro' } },
      { component: 'MasteryCheck', content: { questions: [{question:'2 + 2', correct_answer:'4', options:['3','4'], explanation:'sum'}] } },
      { component: 'IndependentProblem', content: { problem: '3 + 2', correct_answer:'5' } },
    ]);
    expect(result.map(item => item.key)).toEqual(['1_q0','2']);
    expect(result[1].prompt).toBe('3 + 2');
  });
});
