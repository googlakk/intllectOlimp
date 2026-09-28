export type HiddenRule = { kind: 'affine' | 'square' | 'absolute'; multiplier: number; offset: number };
export type MachineOperation = { id: string; label: string; kind: 'add' | 'subtract' | 'multiply' | 'divide'; value: number };
export type RuleSpec = { rule: HiddenRule; examples: number[]; challenge_inputs: number[] };
export type MachineSpec = { inputs: number[]; target_outputs: number[]; operations: MachineOperation[]; solution: string[]; max_steps: number };

const OUTPUT_LIMIT = 1_000_000;
export const isBoundedNumber = (value: unknown, limit = 100): value is number => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= limit;
const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const numbers = (value: unknown, limit = 100): value is number[] => Array.isArray(value) && value.length >= 1 && value.length <= 6 && value.every((item) => isBoundedNumber(item, limit));

export function parseNumericAnswer(value: string): number | null {
  const text = value.trim().replace(',', '.');
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return null;
  const result = Number(text);
  return isBoundedNumber(result, OUTPUT_LIMIT) ? result : null;
}

export function applyHiddenRule(rule: HiddenRule, input: number): number | null {
  if (!isBoundedNumber(input) || !isBoundedNumber(rule.multiplier) || !isBoundedNumber(rule.offset)) return null;
  const base = rule.kind === 'affine' ? input : rule.kind === 'square' ? input * input : rule.kind === 'absolute' ? Math.abs(input) : NaN;
  const output = rule.multiplier * base + rule.offset;
  return isBoundedNumber(output, OUTPUT_LIMIT) ? output : null;
}

export function readRuleSpec(value: unknown): RuleSpec | null {
  if (!record(value) || !record(value.rule)) return null;
  const { kind, multiplier, offset } = value.rule;
  if ((kind !== 'affine' && kind !== 'square' && kind !== 'absolute') || !isBoundedNumber(multiplier) || !isBoundedNumber(offset)) return null;
  if (!numbers(value.examples) || !numbers(value.challenge_inputs)) return null;
  const examples = value.examples;
  if (new Set(examples).size !== examples.length) return null;
  const rule: HiddenRule = { kind, multiplier, offset };
  if ([...value.examples, ...value.challenge_inputs].some((input) => applyHiddenRule(rule, input) === null)) return null;
  if (new Set(value.challenge_inputs).size !== value.challenge_inputs.length || value.challenge_inputs.some((input) => examples.includes(input))) return null;
  return { rule, examples: value.examples, challenge_inputs: value.challenge_inputs };
}

export function matchingOutputs(actual: number[], target: number[]): boolean {
  return actual.length > 0 && actual.length === target.length && actual.every((value, index) => isBoundedNumber(value, OUTPUT_LIMIT) && isBoundedNumber(target[index], OUTPUT_LIMIT) && Math.abs(value - target[index]) <= 0.000001);
}

export function runMachine(spec: MachineSpec, sequence: string[]): number[][] | null {
  if (!numbers(spec.inputs) || sequence.length < 1 || sequence.length > spec.max_steps || sequence.length > 8) return null;
  const stages = [spec.inputs];
  for (const id of sequence) {
    const operation = spec.operations.find((item) => item.id === id);
    if (!operation || !isBoundedNumber(operation.value) || (operation.kind === 'divide' && operation.value === 0)) return null;
    const next = stages[stages.length - 1].map((input) => {
      switch (operation.kind) {
        case 'add': return input + operation.value;
        case 'subtract': return input - operation.value;
        case 'multiply': return input * operation.value;
        case 'divide': return input / operation.value;
        default: return NaN;
      }
    });
    if (!next.every((output) => isBoundedNumber(output, OUTPUT_LIMIT))) return null;
    stages.push(next);
  }
  return stages;
}

export function readMachineSpec(value: unknown): MachineSpec | null {
  if (!record(value) || !numbers(value.inputs) || !numbers(value.target_outputs, OUTPUT_LIMIT) || value.inputs.length !== value.target_outputs.length) return null;
  if (!Number.isInteger(value.max_steps) || typeof value.max_steps !== 'number' || value.max_steps < 1 || value.max_steps > 8) return null;
  if (!Array.isArray(value.operations) || value.operations.length < 1 || value.operations.length > 8) return null;
  const operations: MachineOperation[] = [];
  for (const item of value.operations) {
    if (!record(item) || typeof item.id !== 'string' || !item.id.trim() || typeof item.label !== 'string' || !item.label.trim() || !isBoundedNumber(item.value)) return null;
    if (item.kind !== 'add' && item.kind !== 'subtract' && item.kind !== 'multiply' && item.kind !== 'divide') return null;
    if (item.kind === 'divide' && item.value === 0) return null;
    operations.push({ id: item.id, label: item.label, kind: item.kind, value: item.value });
  }
  if (new Set(operations.map((item) => item.id)).size !== operations.length) return null;
  if (!Array.isArray(value.solution) || !value.solution.every((id): id is string => typeof id === 'string')) return null;
  const spec = { inputs: value.inputs, target_outputs: value.target_outputs, operations, solution: value.solution, max_steps: value.max_steps };
  const stages = runMachine(spec, spec.solution);
  return stages && matchingOutputs(stages[stages.length - 1], spec.target_outputs) ? spec : null;
}

export const displayNumber = (value: number) => Number(value.toFixed(6)).toLocaleString('ru-RU', { maximumFractionDigits: 6 });
