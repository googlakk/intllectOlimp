import React, { useMemo } from 'react';
import { RichText } from './RichText';

export interface MindMapBranch {
  label: string;
  children: string[];
}

export interface MindMapProps {
  title: string;
  central_concept: string;
  branches: MindMapBranch[];
}

const ROOT_WIDTH = 224;
const BRANCH_WIDTH = 200;
const LEAF_WIDTH = 184;
const NODE_HEIGHT = 72;
const LEVEL_GAP = 72;
const LEAF_GAP = 28;
const ROW_GAP = 30;
const PADDING_X = 48;
const PADDING_Y = 42;

export interface HorizontalMindMapNode {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  kind: 'root' | 'branch' | 'leaf';
}

export interface HorizontalMindMapRow {
  branch: HorizontalMindMapNode;
  leaves: HorizontalMindMapNode[];
}

export interface HorizontalMindMapLayout {
  root: HorizontalMindMapNode;
  rows: HorizontalMindMapRow[];
  width: number;
  height: number;
}

export function buildHorizontalMindMapLayout(
  centralConcept: string,
  branches: MindMapBranch[],
): HorizontalMindMapLayout {
  const safeBranches = branches.length > 0 ? branches : [{ label: '', children: [] }];
  const rowPitch = NODE_HEIGHT + ROW_GAP;
  const contentHeight = safeBranches.length * NODE_HEIGHT + Math.max(0, safeBranches.length - 1) * ROW_GAP;
  const rootY = PADDING_Y + contentHeight / 2 - NODE_HEIGHT / 2;
  const branchX = PADDING_X + ROOT_WIDTH + LEVEL_GAP;
  const firstLeafX = branchX + BRANCH_WIDTH + LEVEL_GAP;

  const rows = safeBranches.map((branch, branchIndex) => {
    const y = PADDING_Y + branchIndex * rowPitch;
    return {
      branch: {
        id: `branch-${branchIndex}`,
        label: branch.label,
        x: branchX,
        y,
        width: BRANCH_WIDTH,
        kind: 'branch' as const,
      },
      leaves: (branch.children || []).map((label, leafIndex) => ({
        id: `leaf-${branchIndex}-${leafIndex}`,
        label,
        x: firstLeafX + leafIndex * (LEAF_WIDTH + LEAF_GAP),
        y,
        width: LEAF_WIDTH,
        kind: 'leaf' as const,
      })),
    };
  });

  const maxLeafCount = Math.max(0, ...rows.map((row) => row.leaves.length));
  const contentRight = maxLeafCount > 0
    ? firstLeafX + maxLeafCount * LEAF_WIDTH + Math.max(0, maxLeafCount - 1) * LEAF_GAP
    : branchX + BRANCH_WIDTH;

  return {
    root: {
      id: 'root',
      label: centralConcept,
      x: PADDING_X,
      y: rootY,
      width: ROOT_WIDTH,
      kind: 'root',
    },
    rows: branches.length > 0 ? rows : [],
    width: contentRight + PADDING_X,
    height: Math.max(NODE_HEIGHT + PADDING_Y * 2, contentHeight + PADDING_Y * 2),
  };
}

function nodeColors(kind: HorizontalMindMapNode['kind']) {
  if (kind === 'root') {
    return {
      fill: 'hsl(var(--primary) / 0.1)',
      stroke: 'hsl(var(--primary))',
      strokeWidth: 2,
      textClass: 'font-semibold text-foreground',
    };
  }
  if (kind === 'leaf') {
    return {
      fill: 'hsl(var(--muted) / 0.55)',
      stroke: 'hsl(var(--border))',
      strokeWidth: 1,
      textClass: 'font-normal text-muted-foreground',
    };
  }
  return {
    fill: 'hsl(var(--card))',
    stroke: 'hsl(var(--primary) / 0.28)',
    strokeWidth: 1.5,
    textClass: 'font-medium text-foreground',
  };
}

function MapNode({ node }: { node: HorizontalMindMapNode }) {
  const colors = nodeColors(node.kind);
  return (
    <g transform={`translate(${node.x}, ${node.y})`} className="group cursor-default">
      <rect
        width={node.width}
        height={NODE_HEIGHT}
        rx="10"
        fill={colors.fill}
        stroke={colors.stroke}
        strokeWidth={colors.strokeWidth}
        className="transition-colors duration-200 group-hover:stroke-[hsl(var(--primary)/0.7)]"
      />
      <foreignObject width={node.width} height={NODE_HEIGHT}>
        <div className={`pointer-events-none flex h-full w-full select-none items-center justify-center overflow-hidden px-4 text-center font-sans text-sm leading-snug ${colors.textClass}`}>
          <RichText text={node.label} inline />
        </div>
      </foreignObject>
      <title>{node.label}</title>
    </g>
  );
}

export default function MindMap({ title, central_concept, branches }: MindMapProps) {
  const layout = useMemo(
    () => buildHorizontalMindMapLayout(central_concept, branches),
    [central_concept, branches],
  );

  if (!central_concept) return null;

  const rootStartX = layout.root.x + layout.root.width;
  const rootStartY = layout.root.y + NODE_HEIGHT / 2;

  return (
    <section className="my-6 overflow-hidden rounded-lg border border-border bg-muted/10 shadow-sm" data-layout-direction="horizontal">
      <header className="border-b border-border bg-card px-4 py-3">
        <h3 className="text-base font-semibold text-foreground"><RichText text={title} inline /></h3>
      </header>

      {/* Телефон: схема шире экрана, и видно только главное понятие — показываем её списком сверху вниз. */}
      <div className="space-y-3 p-4 sm:hidden">
        <div className="rounded-xl border-2 border-primary bg-primary/10 px-4 py-3 text-center font-semibold">
          <RichText text={central_concept} inline />
        </div>
        {branches.map((branch, index) => (
          <div key={index} className="ml-3 border-l-2 border-primary/30 pl-3">
            <div className="rounded-lg border border-primary/30 bg-card px-3 py-2 text-sm font-medium"><RichText text={branch.label} inline /></div>
            {(branch.children || []).length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-2">
                {branch.children.map((child, childIndex) => (
                  <li key={childIndex} className="rounded-lg border bg-muted/50 px-3 py-1.5 text-sm text-muted-foreground"><RichText text={child} inline /></li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      <div className="relative hidden w-full overflow-x-auto overscroll-x-contain sm:block" tabIndex={0} aria-label="Горизонтальная карта связей">
        <svg
          width={layout.width}
          height={layout.height}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="img"
          aria-label={`${title}: ${central_concept}`}
          className="block min-w-full"
        >
          <g fill="none" stroke="hsl(var(--primary) / 0.34)" strokeLinecap="round">
            {layout.rows.map(({ branch, leaves }) => {
              const branchCenterY = branch.y + NODE_HEIGHT / 2;
              const rootControlX = rootStartX + LEVEL_GAP / 2;
              const lastLeaf = leaves.at(-1);
              return (
                <React.Fragment key={`connections-${branch.id}`}>
                  <path
                    d={`M ${rootStartX} ${rootStartY} C ${rootControlX} ${rootStartY}, ${rootControlX} ${branchCenterY}, ${branch.x} ${branchCenterY}`}
                    strokeWidth="2.5"
                  />
                  {lastLeaf && (
                    <path
                      d={`M ${branch.x + branch.width} ${branchCenterY} H ${lastLeaf.x}`}
                      strokeWidth="1.75"
                    />
                  )}
                </React.Fragment>
              );
            })}
          </g>

          <MapNode node={layout.root} />
          {layout.rows.flatMap(({ branch, leaves }) => [
            <MapNode key={branch.id} node={branch} />,
            ...leaves.map((leaf) => <MapNode key={leaf.id} node={leaf} />),
          ])}
        </svg>
      </div>
      <p className="sr-only">Карта читается слева направо: главное понятие, ветвь и связанные с ней идеи.</p>
    </section>
  );
}
