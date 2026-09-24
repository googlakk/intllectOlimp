import type { Block } from '@/lib/api';
export type AssessmentQuestion = { key: string; prompt: string; options: string[]; correctAnswer: string; explanation: string };
export function assessmentQuestions(blocks: Block[]): AssessmentQuestion[] {
  return blocks.flatMap((block, index) => {
    const content = block.content;
    const make = (item: Record<string, unknown>, key: string): AssessmentQuestion => ({
      key, prompt: String(item.question ?? item.problem ?? item.task ?? ''),
      options: Array.isArray(item.options) ? item.options.map(String) : [],
      correctAnswer: String(item.correct_answer ?? ''), explanation: String(item.explanation ?? item.solution ?? ''),
    });
    if (block.component === 'MasteryCheck' && Array.isArray(content.questions)) {
      return content.questions.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
        .map((item, questionIndex) => make(item, `${index}_q${questionIndex}`));
    }
    return ['RetrievalCheck', 'IndependentProblem'].includes(block.component) ? [make(content, String(index))] : [];
  });
}
