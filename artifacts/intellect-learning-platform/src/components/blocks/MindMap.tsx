import React, { useMemo } from 'react';

export interface MindMapBranch {
  label: string;
  children: string[];
}

export interface MindMapProps {
  title: string;
  central_concept: string;
  branches: MindMapBranch[];
}

const ROOT_WIDTH = 220;
const NODE_WIDTH = 180;
const LEAF_WIDTH = 140;
const NODE_HEIGHT = 56;
const LEVEL_GAP = 80;
const SIBLING_GAP = 24;
const PADDING = 60;

interface PositionedNode {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  isRoot?: boolean;
  isLeaf?: boolean;
  subtreeHeight: number;
  children: PositionedNode[];
}

export default function MindMap({ title, central_concept, branches }: MindMapProps) {
  const { positionedRoot, width, height } = useMemo(() => {
    if (!central_concept) return { positionedRoot: null, width: 0, height: 0 };
    
    // Build tree
    const rootTree = {
      id: 'root',
      label: central_concept,
      isRoot: true,
      children: branches.map((branch, i) => ({
        id: `branch-${i}`,
        label: branch.label,
        children: (branch.children || []).map((leaf, j) => ({
          id: `leaf-${i}-${j}`,
          label: leaf,
          isLeaf: true,
          children: []
        }))
      }))
    };

    // Calculate heights
    const calcHeights = (node: any): any => {
      if (!node.children || node.children.length === 0) {
        return { ...node, subtreeHeight: NODE_HEIGHT, width: node.isLeaf ? LEAF_WIDTH : NODE_WIDTH };
      }
      
      const children = node.children.map(calcHeights);
      const h = children.reduce((sum: number, c: any) => sum + c.subtreeHeight, 0) + (children.length - 1) * SIBLING_GAP;
      
      return { 
        ...node, 
        children, 
        subtreeHeight: Math.max(NODE_HEIGHT, h),
        width: node.isRoot ? ROOT_WIDTH : NODE_WIDTH
      };
    };

    const treeWithHeights = calcHeights(rootTree);
    const totalHeight = treeWithHeights.subtreeHeight;
    
    // Assign positions
    const assignPos = (node: any, x: number, yCenter: number): PositionedNode => {
      const children = node.children || [];
      const posChildren: PositionedNode[] = [];
      
      if (children.length > 0) {
        const totalChildrenHeight = children.reduce((sum: number, c: any) => sum + c.subtreeHeight, 0) + (children.length - 1) * SIBLING_GAP;
        let currentY = yCenter - totalChildrenHeight / 2;
        
        for (const child of children) {
          const childCenter = currentY + child.subtreeHeight / 2;
          posChildren.push(assignPos(child, x + node.width + LEVEL_GAP, childCenter));
          currentY += child.subtreeHeight + SIBLING_GAP;
        }
      }

      return {
        ...node,
        x,
        y: yCenter - NODE_HEIGHT / 2,
        children: posChildren,
      };
    };

    // Depth is max 2 (root -> branch -> leaf)
    // Width = ROOT_WIDTH + LEVEL_GAP + NODE_WIDTH + LEVEL_GAP + LEAF_WIDTH
    const totalWidth = ROOT_WIDTH + NODE_WIDTH + LEAF_WIDTH + LEVEL_GAP * 2;
    const rootPos = assignPos(treeWithHeights, PADDING, PADDING + totalHeight / 2);
    
    return {
      positionedRoot: rootPos,
      width: totalWidth + PADDING * 2,
      height: totalHeight + PADDING * 2,
    };
  }, [central_concept, branches]);

  if (!positionedRoot) return null;

  const renderEdges = (node: PositionedNode): React.ReactNode[] => {
    const edges: React.ReactNode[] = [];
    const children = node.children;
    
    const startX = node.x + node.width;
    const startY = node.y + NODE_HEIGHT / 2;
    
    children.forEach(child => {
      const endX = child.x;
      const endY = child.y + NODE_HEIGHT / 2;
      
      const controlPointX = startX + LEVEL_GAP / 2;
      const path = `M ${startX} ${startY} C ${controlPointX} ${startY}, ${controlPointX} ${endY}, ${endX} ${endY}`;
      
      edges.push(
        <path
          key={`edge-${node.id}-${child.id}`}
          d={path}
          fill="none"
          stroke="hsl(var(--primary) / 0.3)"
          strokeWidth={node.isRoot ? "3" : "1.5"}
          className="transition-all duration-300"
        />
      );
      
      edges.push(...renderEdges(child));
    });
    
    return edges;
  };

  const renderNodes = (node: PositionedNode): React.ReactNode[] => {
    const nodes: React.ReactNode[] = [];
    
    let bgClass = "hsl(var(--card))";
    let strokeClass = "hsl(var(--primary) / 0.2)";
    let textClass = "hsl(var(--foreground))";
    let fontWeight = "500";
    
    if (node.isRoot) {
      bgClass = "hsl(var(--primary) / 0.1)";
      strokeClass = "hsl(var(--primary))";
      textClass = "hsl(var(--foreground))";
      fontWeight = "600";
    } else if (node.isLeaf) {
      bgClass = "hsl(var(--muted) / 0.5)";
      strokeClass = "transparent";
      textClass = "hsl(var(--muted-foreground))";
      fontWeight = "400";
    }

    nodes.push(
      <g key={`node-${node.id}`} transform={`translate(${node.x}, ${node.y})`} className="group cursor-default">
        <rect
          width={node.width}
          height={NODE_HEIGHT}
          rx={node.isLeaf ? "8" : "12"}
          fill={bgClass}
          stroke={strokeClass}
          strokeWidth={node.isRoot ? "2" : "1"}
          className={!node.isLeaf ? "group-hover:stroke-[hsl(var(--primary)/0.6)] transition-all duration-300 drop-shadow-sm" : ""}
        />
        <text
          x={node.width / 2}
          y={NODE_HEIGHT / 2}
          textAnchor="middle"
          dominantBaseline="central"
          fill={textClass}
          fontSize={node.isRoot ? "16" : node.isLeaf ? "13" : "14"}
          fontWeight={fontWeight}
          className="pointer-events-none select-none font-sans"
        >
          {node.label.length > (node.isRoot ? 25 : 20) ? node.label.substring(0, (node.isRoot ? 23 : 18)) + '...' : node.label}
        </text>
        <title>{node.label}</title>
      </g>
    );
    
    node.children.forEach(child => {
      nodes.push(...renderNodes(child));
    });
    
    return nodes;
  };

  return (
    <div className="my-8 border rounded-2xl bg-muted/10 overflow-hidden shadow-inner relative">
      <div className="p-4 border-b bg-background/50 backdrop-blur-sm relative z-20">
        <h3 className="font-semibold text-lg text-foreground">{title}</h3>
      </div>
      
      <div className="absolute left-0 top-14 bottom-0 w-8 bg-gradient-to-r from-background to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-14 bottom-0 w-8 bg-gradient-to-l from-background to-transparent z-10 pointer-events-none" />
      
      <div 
        className="overflow-x-auto overflow-y-auto custom-scrollbar w-full relative z-0" 
        style={{ maxHeight: '600px' }}
      >
        <svg 
          width={width} 
          height={height} 
          className="min-w-max" 
          style={{ display: 'block' }}
        >
          <g>
            {renderEdges(positionedRoot)}
            {renderNodes(positionedRoot)}
          </g>
        </svg>
      </div>
    </div>
  );
}
