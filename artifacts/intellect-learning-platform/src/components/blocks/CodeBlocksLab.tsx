import * as Blockly from 'blockly/core';
import 'blockly/blocks';
import { javascriptGenerator } from 'blockly/javascript';
import * as Ru from 'blockly/msg/ru';

// blockly/core идёт без текстов: без локали блоки падают при создании (подписи для экранного диктора).
// Русские тексты — ещё и понятнее ученику.
Blockly.setLocale(Ru as unknown as Record<string, string>);
import { useEffect, useRef, useState } from 'react';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { type BlockResult } from '@/features/interactiveEngines/scoring';

export interface CodeBlocksLabProps {
  title: string;
  task: string;
  toolbox_xml: string;
  expected_block_types: string[];
  explanation: string;
  starter_xml?: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function CodeBlocksLab({ title, task, toolbox_xml, expected_block_types, explanation, starter_xml, onAnswer }: CodeBlocksLabProps) {
  const divRef = useRef<HTMLDivElement | null>(null);
  const workspaceRef = useRef<Blockly.WorkspaceSvg | null>(null);
  const [code, setCode] = useState('');
  const [result, setResult] = useState<BlockResult>('idle');

  useEffect(() => {
    if (!divRef.current) return undefined;
    const toolbox = Blockly.utils.xml.textToDom(toolbox_xml);
    // Узкий экран: палитра сбоку съедает почти всю ширину — ставим её сверху, блоки мельче.
    const narrow = divRef.current.clientWidth < 560;
    const workspace = Blockly.inject(divRef.current, {
      toolbox,
      horizontalLayout: narrow,
      toolboxPosition: 'start',
      grid: { spacing: 20, length: 3, colour: '#cbd5e1', snap: true },
      trashcan: true,
      zoom: { controls: true, wheel: true, startScale: narrow ? 0.8 : 1 },
      move: { scrollbars: true, drag: true, wheel: false },
    });
    if (starter_xml) {
      Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(starter_xml), workspace);
    }
    workspaceRef.current = workspace;
    const listener = () => setCode(javascriptGenerator.workspaceToCode(workspace));
    workspace.addChangeListener(listener);
    listener();
    return () => {
      workspace.removeChangeListener(listener);
      workspace.dispose();
      workspaceRef.current = null;
    };
  }, [starter_xml, toolbox_xml]);

  const check = () => {
    const workspace = workspaceRef.current;
    const present = new Set(workspace?.getAllBlocks(false).map((block) => block.type) || []);
    const ok = expected_block_types.every((type) => present.has(type));
    setResult(ok ? 'correct' : 'incorrect');
    onAnswer?.(ok);
  };

  return (
    <BlockShell title={title} subtitle={task}>
      <div ref={divRef} className="h-[460px] overflow-hidden rounded-xl border border-border bg-background sm:h-[420px]" />
      <div className="mt-4 rounded-lg border border-border bg-muted/20 p-4">
        <h4 className="mb-2 text-sm font-bold text-foreground">Получившийся JavaScript</h4>
        <pre className="max-h-40 overflow-auto rounded bg-background p-3 text-xs text-muted-foreground">{code || '// Соберите алгоритм из блоков'}</pre>
      </div>
      <div className="mt-5 flex justify-end">
        <PrimaryAction onClick={check}>Проверить алгоритм</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} incorrectText={explanation} />
    </BlockShell>
  );
}
