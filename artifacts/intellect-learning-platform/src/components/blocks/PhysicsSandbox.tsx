import Matter from 'matter-js';
import { useEffect, useRef, useState } from 'react';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { normalizeText, type BlockResult } from '@/features/interactiveEngines/scoring';

export type PhysicsBody = {
  shape: 'circle' | 'rectangle';
  x: number;
  y: number;
  width?: number;
  height?: number;
  radius?: number;
  is_static?: boolean;
  label?: string;
};

export type PhysicsParam = {
  name: 'gravity' | 'restitution';
  label: string;
  min: number;
  max: number;
  step: number;
  default: number;
};

export interface PhysicsSandboxProps {
  title: string;
  prompt: string;
  bodies: PhysicsBody[];
  params: PhysicsParam[];
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function PhysicsSandbox({ title, prompt, bodies, params, question, options, correct_answer, explanation, onAnswer }: PhysicsSandboxProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [values, setValues] = useState(() => Object.fromEntries(params.map((param) => [param.name, param.default])));
  const [version, setVersion] = useState(0);
  const [selected, setSelected] = useState('');
  const [result, setResult] = useState<BlockResult>('idle');

  useEffect(() => {
    if (!hostRef.current) return undefined;
    hostRef.current.innerHTML = '';
    const engine = Matter.Engine.create();
    engine.gravity.y = Number(values.gravity ?? 1);
    const render = Matter.Render.create({
      element: hostRef.current,
      engine,
      options: {
        width: 720,
        height: 360,
        wireframes: false,
        background: 'transparent',
      },
    });
    // Мир всегда 720×360, а холст сжимается под ширину экрана: на телефоне видна вся сцена, а не её середина.
    render.canvas.style.width = '100%';
    render.canvas.style.height = 'auto';
    render.canvas.style.display = 'block';
    const worldBodies = bodies.map((body) => {
      const options = {
        isStatic: body.is_static === true,
        restitution: Number(values.restitution ?? 0.5),
        render: { fillStyle: body.is_static ? '#94a3b8' : '#4f46e5' },
      };
      return body.shape === 'circle'
        ? Matter.Bodies.circle(body.x, body.y, body.radius || 24, options)
        : Matter.Bodies.rectangle(body.x, body.y, body.width || 90, body.height || 24, options);
    });
    Matter.Composite.add(engine.world, worldBodies);
    const runner = Matter.Runner.create();
    Matter.Render.run(render);
    Matter.Runner.run(runner, engine);
    return () => {
      Matter.Render.stop(render);
      Matter.Runner.stop(runner);
      Matter.World.clear(engine.world, false);
      Matter.Engine.clear(engine);
      render.canvas.remove();
      render.textures = {};
    };
  }, [bodies, values, version]);

  const check = () => {
    const ok = normalizeText(selected) === normalizeText(correct_answer);
    setResult(ok ? 'correct' : 'incorrect');
    onAnswer?.(ok);
  };

  return (
    <BlockShell title={title} subtitle={prompt}>
      <div className="overflow-hidden rounded-xl border border-border bg-background">
        <div ref={hostRef} className="mx-auto w-full max-w-[720px]" />
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {params.map((param) => (
          <label key={param.name} className="rounded-lg border border-border bg-muted/20 p-4 text-sm font-semibold">
            <div className="flex justify-between gap-3">
              <RichText text={param.label} inline />
              <span className="font-mono text-primary">{Number(values[param.name]).toFixed(2)}</span>
            </div>
            <input
              className="mt-3 w-full accent-primary"
              type="range"
              min={param.min}
              max={param.max}
              step={param.step}
              value={values[param.name]}
              onChange={(event) => setValues((current) => ({ ...current, [param.name]: Number(event.target.value) }))}
            />
          </label>
        ))}
      </div>
      <div className="mt-4 flex justify-end">
        <button className="rounded-lg border border-border px-4 py-2 text-sm font-bold hover:bg-muted" onClick={() => setVersion((item) => item + 1)}>
          Запустить заново
        </button>
      </div>
      <div className="mt-5 rounded-lg border border-border bg-muted/20 p-4">
        <h4 className="mb-3 text-sm font-bold text-foreground"><RichText text={question} inline /></h4>
        <div className="grid gap-2 md:grid-cols-2">
          {options.map((option) => (
            <button
              key={option}
              onClick={() => setSelected(option)}
              className={`rounded-lg border p-3 text-left text-sm font-semibold transition ${selected === option ? 'border-primary bg-primary/10' : 'border-border bg-card hover:border-primary/30'}`}
            >
              <RichText text={option} inline />
            </button>
          ))}
        </div>
      </div>
      <div className="mt-5 flex justify-end">
        <PrimaryAction onClick={check} disabled={!selected}>Проверить наблюдение</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} incorrectText={explanation} />
    </BlockShell>
  );
}
