/**
 * Школьные выражения: разбор ввода ученика и ответа из урока, сверка по смыслу и запись в LaTeX.
 * Ввод: 2√3, √(x+1), sqrt(12), 3/4, (a+b)^2, x², 0,5x, 2·3, 6:2, а также LaTeX из урока (\frac{1}{2}, \sqrt{3}).
 * Равносильность — подстановкой случайных значений переменных: 2√3 = √12, x/2 = 0,5x, (a+b)² ≠ a²+b².
 */

export type MathNode =
  | { kind: 'num'; value: number; text: string }
  | { kind: 'var'; name: string }
  | { kind: 'neg'; arg: MathNode }
  | { kind: 'sqrt'; arg: MathNode }
  | { kind: 'bin'; op: '+' | '-' | '*' | '/' | '^'; left: MathNode; right: MathNode };

type Token = { type: 'num'; value: number; text: string } | { type: 'var'; name: string } | { type: 'op'; value: string };

const SUPERSCRIPT_POWERS: Record<string, string> = { '²': '^2', '³': '^3' };

/** LaTeX и «красивые» знаки → простая запись. */
function preprocess(source: string): string {
  let text = source.trim().replace(/^\$+|\$+$/g, '');
  // \frac{a}{b} → ((a)/(b)), \sqrt{a} → √(a); вложенные — повторяем, пока меняется.
  for (let guard = 0; guard < 10; guard += 1) {
    const next = text
      .replace(/\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, '(($1)/($2))')
      .replace(/\\sqrt\s*\{([^{}]*)\}/g, '√($1)');
    if (next === text) break;
    text = next;
  }
  return text
    .replace(/\\cdot|\\times/g, '*')
    .replace(/\\left|\\right|\\,|\\!|\\ /g, '')
    .replace(/sqrt/gi, '√')
    .replace(/[{]/g, '(').replace(/[}]/g, ')')
    .replace(/[²³]/g, (char) => SUPERSCRIPT_POWERS[char])
    .replace(/[−–—]/g, '-')
    .replace(/[×·⋅∙]/g, '*')
    .replace(/[:÷]/g, '/')
    .replace(/\s+/g, '');
}

function tokenize(text: string): Token[] | null {
  const tokens: Token[] = [];
  let index = 0;
  while (index < text.length) {
    const rest = text.slice(index);
    const number = /^\d+(?:[.,]\d+)?/.exec(rest);
    if (number) {
      tokens.push({ type: 'num', value: Number(number[0].replace(',', '.')), text: number[0].replace('.', ',') });
      index += number[0].length;
      continue;
    }
    const char = text[index];
    if (/[a-z]/i.test(char)) {
      tokens.push({ type: 'var', name: char });
    } else if ('+-*/^()√'.includes(char)) {
      tokens.push({ type: 'op', value: char });
    } else {
      return null;
    }
    index += 1;
  }
  return tokens;
}

class Parser {
  private position = 0;
  constructor(private readonly tokens: Token[]) {}

  parse(): MathNode | null {
    const node = this.sum();
    return node && this.position === this.tokens.length ? node : null;
  }

  private peek(): Token | undefined { return this.tokens[this.position]; }
  private isOp(value: string): boolean { const token = this.peek(); return token?.type === 'op' && token.value === value; }

  private sum(): MathNode | null {
    let left = this.product();
    while (left && (this.isOp('+') || this.isOp('-'))) {
      const op = (this.tokens[this.position++] as { value: '+' | '-' }).value;
      const right = this.product();
      if (!right) return null;
      left = { kind: 'bin', op, left, right };
    }
    return left;
  }

  /** Умножение и деление, в том числе неявное: 2x, 2√3, 3(x+1), (a+b)(a-b). */
  private product(): MathNode | null {
    let left = this.unary();
    while (left) {
      if (this.isOp('*') || this.isOp('/')) {
        const op = (this.tokens[this.position++] as { value: '*' | '/' }).value;
        const right = this.unary();
        if (!right) return null;
        left = { kind: 'bin', op, left, right };
        continue;
      }
      const token = this.peek();
      const implicit = token && (token.type !== 'op' || token.value === '(' || token.value === '√');
      if (!implicit) break;
      const right = this.power();
      if (!right) return null;
      left = { kind: 'bin', op: '*', left, right };
    }
    return left;
  }

  private unary(): MathNode | null {
    if (this.isOp('-')) { this.position += 1; const arg = this.unary(); return arg && { kind: 'neg', arg }; }
    if (this.isOp('+')) { this.position += 1; return this.unary(); }
    return this.power();
  }

  private power(): MathNode | null {
    const base = this.atom();
    if (base && this.isOp('^')) {
      this.position += 1;
      const negative = this.isOp('-');
      if (negative) this.position += 1;
      const exponent = this.atom();
      if (!exponent) return null;
      return { kind: 'bin', op: '^', left: base, right: negative ? { kind: 'neg', arg: exponent } : exponent };
    }
    return base;
  }

  private atom(): MathNode | null {
    const token = this.peek();
    if (!token) return null;
    this.position += 1;
    if (token.type === 'num') return { kind: 'num', value: token.value, text: token.text };
    if (token.type === 'var') return { kind: 'var', name: token.name };
    if (token.value === '(') {
      const inner = this.sum();
      if (!inner || !this.isOp(')')) return null;
      this.position += 1;
      return inner;
    }
    if (token.value === '√') {
      // √ действует на ближайший множитель со степенью: √12, √x, √(x+1), √x².
      const arg = this.power();
      return arg && { kind: 'sqrt', arg };
    }
    return null;
  }
}

/** Разобрать выражение; «x = …» в ответе — берём правую часть. null — не выражение (слова, пусто). */
export function parseMath(source: unknown): MathNode | null {
  let text = preprocess(String(source ?? ''));
  const assignment = /^[a-z](?:_?\d)?=(.+)$/i.exec(text);
  if (assignment) text = assignment[1];
  // Только буквы («ab», «ba») — это подпись или слово, а не выражение: сверяем как текст.
  if (!text || text.includes('=') || (text.length > 1 && !/[\d+\-*/^√()]/.test(text))) return null;
  const tokens = tokenize(text);
  return tokens && tokens.length ? new Parser(tokens).parse() : null;
}

function variables(node: MathNode, into = new Set<string>()): Set<string> {
  if (node.kind === 'var') into.add(node.name);
  else if (node.kind === 'neg' || node.kind === 'sqrt') variables(node.arg, into);
  else if (node.kind === 'bin') { variables(node.left, into); variables(node.right, into); }
  return into;
}

export function evaluateMath(node: MathNode, scope: Record<string, number>): number {
  switch (node.kind) {
    case 'num': return node.value;
    case 'var': return scope[node.name] ?? NaN;
    case 'neg': return -evaluateMath(node.arg, scope);
    case 'sqrt': { const value = evaluateMath(node.arg, scope); return value < 0 ? NaN : Math.sqrt(value); }
    case 'bin': {
      const left = evaluateMath(node.left, scope);
      const right = evaluateMath(node.right, scope);
      if (node.op === '+') return left + right;
      if (node.op === '-') return left - right;
      if (node.op === '*') return left * right;
      if (node.op === '/') return right === 0 ? NaN : left / right;
      return left ** right;
    }
  }
}

function close(left: number, right: number): boolean {
  return Math.abs(left - right) <= 1e-7 * Math.max(1, Math.abs(left), Math.abs(right));
}

function balanced(text: string): boolean {
  let depth = 0;
  for (const char of text) {
    depth += char === '(' ? 1 : char === ')' ? -1 : 0;
    if (depth < 0) return false;
  }
  return depth === 0;
}

/**
 * Одна и та же запись: пробелы, знаки умножения, sqrt/√, ², LaTeX и запятая не важны,
 * но 2(x+1) и 2x+2 — разные записи (задания «раскройте скобки», «сократите дробь»).
 */
export function sameForm(left: unknown, right: unknown): boolean {
  const clean = (value: unknown) => {
    let text = preprocess(String(value ?? '')).replace(/\*/g, '').toLocaleLowerCase();
    // Скобки вокруг одного числа или буквы не меняют запись: √(12) = √12, ((3)/(4)) = 3/4.
    for (let guard = 0; guard < 10; guard += 1) {
      const unwrapped = text.replace(/\(([\w.,]+)\)/g, '$1');
      if (unwrapped === text) break;
      text = unwrapped;
    }
    // Скобки вокруг всей записи — тоже: \frac{3}{4} даёт (3/4).
    while (text.startsWith('(') && text.endsWith(')') && balanced(text.slice(1, -1))) text = text.slice(1, -1);
    return text;
  };
  return clean(left) !== '' && clean(left) === clean(right);
}

/**
 * Равны ли выражения по смыслу: одинаковые значения при нескольких подстановках.
 * numbers=false — два простых числа («8,9» и «8.9») по смыслу не сверяем: это решает вопрос.
 */
export function sameMath(left: unknown, right: unknown, { numbers = true }: { numbers?: boolean } = {}): boolean {
  const a = parseMath(left);
  const b = parseMath(right);
  if (!a || !b) return false;
  // «x = 7» — уже запись решения, а не число из варианта ответа.
  if (!numbers && a.kind === 'num' && b.kind === 'num' && !`${left}${right}`.includes('=')) return false;
  const names = [...new Set([...variables(a), ...variables(b)])];
  // Детерминированные «случайные» значения: результат одинаков при каждой проверке.
  const samples = [1.7, 2.3, 3.1, 0.6, 4.4, 1.2, 2.9];
  let compared = 0;
  for (let round = 0; round < samples.length; round += 1) {
    const scope = Object.fromEntries(names.map((name, index) => [name, samples[(round + index * 3) % samples.length]]));
    const x = evaluateMath(a, scope);
    const y = evaluateMath(b, scope);
    if (!Number.isFinite(x) && !Number.isFinite(y)) continue;
    if (!close(x, y)) return false;
    compared += 1;
    if (!names.length) break;
  }
  return compared > 0;
}

function wrap(node: MathNode, latex: string, parentOp: string, side: 'left' | 'right'): string {
  if (node.kind !== 'bin' && node.kind !== 'neg') return latex;
  const rank = (op: string) => (op === '+' || op === '-' ? 1 : op === '*' || op === '/' ? 2 : 3);
  const own = node.kind === 'neg' ? 1 : rank(node.op);
  const needs = own < rank(parentOp) || (side === 'right' && own === rank(parentOp) && parentOp !== '+' && parentOp !== '*');
  return needs ? `\\left(${latex}\\right)` : latex;
}

/** Запись для предпросмотра: дробь — дробью, корень — корнем. */
export function mathToLatex(node: MathNode): string {
  switch (node.kind) {
    case 'num': return node.text;
    case 'var': return node.name;
    case 'neg': return `-${wrap(node.arg, mathToLatex(node.arg), '*', 'right')}`;
    case 'sqrt': return `\\sqrt{${mathToLatex(node.arg)}}`;
    case 'bin': {
      if (node.op === '/') return `\\frac{${mathToLatex(node.left)}}{${mathToLatex(node.right)}}`;
      const left = wrap(node.left, mathToLatex(node.left), node.op, 'left');
      const right = wrap(node.right, mathToLatex(node.right), node.op, 'right');
      if (node.op === '^') return `{${node.left.kind === 'sqrt' || node.left.kind === 'bin' || node.left.kind === 'neg' ? `\\left(${mathToLatex(node.left)}\\right)` : left}}^{${mathToLatex(node.right)}}`;
      if (node.op === '*') {
        // 2x, 2√3, 3(x+1) — без знака; между числами — точка.
        const dot = node.right.kind === 'num' || (node.right.kind === 'bin' && node.right.op === '^' && node.right.left.kind === 'num');
        return `${left}${dot ? ' \\cdot ' : ''}${right}`;
      }
      return `${left} ${node.op} ${right}`;
    }
  }
}
