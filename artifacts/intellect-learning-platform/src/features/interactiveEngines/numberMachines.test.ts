import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { componentDemos } from '@/features/componentCatalog/demos';
import { applyHiddenRule, matchingOutputs, parseNumericAnswer, readMachineSpec, readRuleSpec, runMachine } from './numberMachines';

const rule = { rule: { kind: 'affine', multiplier: 3, offset: 2 }, examples: [0, 1], challenge_inputs: [2, -2] };
const machine = { inputs: [1, 2, 4], target_outputs: [9, 12, 18], operations: [{ id: 'a', label: '+2', kind: 'add', value: 2 }, { id: 'm', label: '×3', kind: 'multiply', value: 3 }], solution: ['a', 'm'], max_steps: 4 };
type SharedCases = { base: Record<string, unknown>; cases: { name: string; patch: Record<string, unknown>; valid: boolean }[] };
const shared = JSON.parse(readFileSync(resolve(__dirname, '../../../../../backend/fixtures/number_machine_cases.json'), 'utf8')) as { rule: SharedCases; machine: SharedCases };

describe('number machines', () => {
  for (const sample of shared.rule.cases) {
    it(`matches server rule contract: ${sample.name}`, () => {
      expect(readRuleSpec({ ...shared.rule.base, ...sample.patch }) !== null).toBe(sample.valid);
    });
  }
  for (const sample of shared.machine.cases) {
    it(`matches server machine contract: ${sample.name}`, () => {
      expect(readMachineSpec({ ...shared.machine.base, ...sample.patch }) !== null).toBe(sample.valid);
    });
  }
  it('uses validated runnable demo specifications', () => {
    expect(readRuleSpec(componentDemos['rule-discovery'].block.content)).not.toBeNull();
    expect(readMachineSpec(componentDemos['transformation-machine'].block.content)).not.toBeNull();
  });
  it('computes affine, squared and absolute rules on signed inputs', () => {
    expect(applyHiddenRule({ kind: 'affine', multiplier: 3, offset: 2 }, -2)).toBe(-4);
    expect(applyHiddenRule({ kind: 'square', multiplier: 2, offset: -1 }, -3)).toBe(17);
    expect(applyHiddenRule({ kind: 'absolute', multiplier: -2, offset: 1 }, -3)).toBe(-5);
  });
  it('rejects unsafe numbers and leaked challenge examples', () => {
    expect(readRuleSpec(rule)).not.toBeNull();
    expect(readRuleSpec({ ...rule, examples: [2] })).toBeNull();
    expect(readRuleSpec({ ...rule, challenge_inputs: [3, 3] })).toBeNull();
    expect(readRuleSpec({ ...rule, rule: { kind: 'square', multiplier: Infinity, offset: 0 } })).toBeNull();
    expect(applyHiddenRule({ kind: 'square', multiplier: 100, offset: 100 }, 100)).toBeNull();
  });
  it('requires numeric answers and accepts decimal comma without treating blank as zero', () => {
    expect(parseNumericAnswer(' ')).toBeNull();
    expect(parseNumericAnswer('2abc')).toBeNull();
    expect(parseNumericAnswer('1,25')).toBe(1.25);
    expect(parseNumericAnswer('0')).toBe(0);
    expect(matchingOutputs([], [])).toBe(false);
    expect(matchingOutputs([Infinity], [Infinity])).toBe(false);
    expect(matchingOutputs([1 / 3], [0.333333])).toBe(true);
  });
  it('preserves operation order and returns every intermediate stage', () => {
    const spec = readMachineSpec(machine)!;
    expect(runMachine(spec, ['a', 'm'])).toEqual([[1, 2, 4], [3, 4, 6], [9, 12, 18]]);
    expect(runMachine(spec, ['m', 'a'])?.at(-1)).toEqual([5, 8, 14]);
    expect(runMachine(spec, ['a', 'a'])?.at(-1)).toEqual([5, 6, 8]);
    expect(runMachine(spec, ['missing'])).toBeNull();
    expect(runMachine(spec, [])).toBeNull();
    expect(runMachine(spec, ['a', 'a', 'a', 'a', 'a'])).toBeNull();
  });
  it('checks reachability and division safety before presenting a task', () => {
    expect(readMachineSpec({ ...machine, target_outputs: [0, 0, 0] })).toBeNull();
    expect(readMachineSpec({ ...machine, operations: [{ id: 'a', label: 'divide', kind: 'divide', value: 0 }] })).toBeNull();
    expect(readMachineSpec({ ...machine, max_steps: 9 })).toBeNull();
    expect(readMachineSpec({ ...machine, operations: [...machine.operations, machine.operations[0]] })).toBeNull();
    const spec = readMachineSpec({ inputs: [8, -4], target_outputs: [3, -3], operations: [{ id: 'd', label: '÷2', kind: 'divide', value: 2 }, { id: 's', label: '−1', kind: 'subtract', value: 1 }], solution: ['d', 's'], max_steps: 2 });
    expect(spec && runMachine(spec, spec.solution)?.at(-1)).toEqual([3, -3]);
    const overflow = readMachineSpec({ ...machine, operations: [{ id: 'a', label: '+2', kind: 'add', value: 2 }, { id: 'm', label: '×3', kind: 'multiply', value: 3 }, { id: 'large', label: '×100', kind: 'multiply', value: 100 }] })!;
    expect(runMachine(overflow, ['large', 'large', 'large', 'large'])).toBeNull();
  });
});
