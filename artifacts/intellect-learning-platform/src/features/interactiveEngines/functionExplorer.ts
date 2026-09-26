/**
 * «График по формуле»: функция с параметрами (y = kx + b, y = a·x², y = k/x, y = √x),
 * ползунки, прогноз «что будет с графиком» до движения ползунка и график-цель пунктиром.
 */
import { evaluateMath, parseExpression, variables, type MathNode } from './mathExpression';

export type ExplorerParam = { name: string; label: string; min: number; max: number; step: number; initial: number };
export type ExplorerPrediction = { question: string; options: string[]; correctAnswer: string; explanation: string };
export type ExplorerPoint = { x: number; y: number; label?: string };
export type Explorer = {
  formula: MathNode;
  formulaText: string;
  params: ExplorerParam[];
  xRange: [number, number];
  yRange: [number, number];
  target: Record<string, number> | null;
  points: ExplorerPoint[];
  prediction: ExplorerPrediction | null;
};

const number = (value: unknown, fallback: number) => (typeof value === 'number' && Number.isFinite(value) ? value : fallback);

function range(value: unknown, fallback: [number, number]): [number, number] {
  if (!Array.isArray(value) || value.length !== 2) return fallback;
  const [low, high] = [number(value[0], NaN), number(value[1], NaN)];
  return Number.isFinite(low) && Number.isFinite(high) && low < high ? [low, high] : fallback;
}

/** Данные блока от модели. null — формула не читается или в ней неизвестные буквы. */
export function normalizeExplorer(content: Record<string, unknown>): Explorer | null {
  const formulaText = String(content.formula ?? '').replace(/^\s*y\s*=\s*/i, '').trim();
  const formula = parseExpression(formulaText);
  if (!formula) return null;
  const params = (Array.isArray(content.params) ? content.params : [])
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => {
      const min = number(item.min, -5);
      const max = number(item.max, 5);
      const step = number(item.step, 0.5) > 0 ? number(item.step, 0.5) : 0.5;
      const initial = Math.min(max, Math.max(min, number(item.default, (min + max) / 2)));
      return { name: String(item.name ?? '').trim(), label: String(item.label ?? item.name ?? ''), min, max, step, initial };
    })
    .filter((param) => /^[a-wz]$/i.test(param.name) && param.min < param.max);
  const known = new Set(['x', ...params.map((param) => param.name)]);
  if ([...variables(formula)].some((name) => !known.has(name))) return null;
  const rawTarget = content.target && typeof content.target === 'object' ? (content.target as Record<string, unknown>).params : null;
  const target = rawTarget && typeof rawTarget === 'object'
    ? Object.fromEntries(params.map((param) => [param.name, number((rawTarget as Record<string, unknown>)[param.name], NaN)]))
    : null;
  const validTarget = target && Object.values(target).every(Number.isFinite) ? target : null;
  const rawPrediction = content.prediction && typeof content.prediction === 'object' ? content.prediction as Record<string, unknown> : null;
  const options = Array.isArray(rawPrediction?.options) ? rawPrediction!.options.map(String) : [];
  const prediction = rawPrediction && options.length >= 2 && options.includes(String(rawPrediction.correct_answer))
    ? { question: String(rawPrediction.question ?? ''), options, correctAnswer: String(rawPrediction.correct_answer), explanation: String(rawPrediction.explanation ?? '') }
    : null;
  const points = (Array.isArray(content.points) ? content.points : [])
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => ({ x: number(item.x, NaN), y: number(item.y, NaN), label: item.label ? String(item.label) : undefined }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  return {
    formula, formulaText, params,
    xRange: range(content.x_range, [-6, 6]),
    yRange: range(content.y_range, [-6, 6]),
    target: validTarget, points, prediction,
  };
}

/** Кривая отрезками: разрыв там, где функция не определена или уходит за край (у гиперболы — около нуля). */
export function sampleCurve(formula: MathNode, values: Record<string, number>, xRange: [number, number], yRange: [number, number], count = 400): ExplorerPoint[][] {
  const segments: ExplorerPoint[][] = [];
  let current: ExplorerPoint[] = [];
  const span = yRange[1] - yRange[0];
  for (let index = 0; index <= count; index += 1) {
    const x = xRange[0] + ((xRange[1] - xRange[0]) * index) / count;
    const y = evaluateMath(formula, { ...values, x });
    const previous = current[current.length - 1];
    const jump = previous && Math.abs(y - previous.y) > span * 2;
    if (!Number.isFinite(y) || jump || Math.abs(y) > span * 20) {
      if (current.length > 1) segments.push(current);
      current = Number.isFinite(y) && Math.abs(y) <= span * 20 ? [{ x, y }] : [];
      continue;
    }
    current.push({ x, y });
  }
  if (current.length > 1) segments.push(current);
  return segments;
}

/** Ползунки стоят на значениях цели (с точностью до половины шага). */
export function reachedTarget(values: Record<string, number>, target: Record<string, number> | null, params: ExplorerParam[]): boolean {
  if (!target) return false;
  return params.every((param) => Math.abs((values[param.name] ?? NaN) - target[param.name]) <= param.step / 2 + 1e-9);
}

/** Формула с подставленными значениями параметров — для подписи «y = 2x − 1». */
export function substituteParams(node: MathNode, values: Record<string, number>): MathNode {
  switch (node.kind) {
    case 'var': {
      if (!(node.name in values)) return node;
      const value = values[node.name];
      const text = String(Math.abs(value)).replace('.', ',');
      const literal: MathNode = { kind: 'num', value: Math.abs(value), text };
      return value < 0 ? { kind: 'neg', arg: literal } : literal;
    }
    case 'num': return node;
    case 'neg':
    case 'sqrt': return { ...node, arg: substituteParams(node.arg, values) };
    case 'bin': return { ...node, left: substituteParams(node.left, values), right: substituteParams(node.right, values) };
  }
}
