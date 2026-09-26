/** «Причины и следствия»: роли факторов, нормализация данных модели, оценка. */

export const CAUSE_ROLES = ['cause', 'trigger', 'consequence', 'unrelated'] as const;
export type CauseRole = (typeof CAUSE_ROLES)[number];

export const ROLE_LABELS: Record<CauseRole, string> = {
  cause: 'Причина', trigger: 'Повод', consequence: 'Последствие', unrelated: 'Не связано',
};

export const KIND_LABELS: Record<string, string> = {
  political: 'политическая', economic: 'экономическая', social: 'социальная', external: 'внешняя', cultural: 'культурная',
};

// Модель пишет роль по-разному: «Cause», «trigger », «причина», «себеп».
const ROLE_ALIASES: Record<string, CauseRole> = {
  cause: 'cause', причина: 'cause', себеп: 'cause',
  trigger: 'trigger', повод: 'trigger', шылтоо: 'trigger',
  consequence: 'consequence', последствие: 'consequence', следствие: 'consequence', натыйжа: 'consequence',
  unrelated: 'unrelated', 'не связано': 'unrelated', 'байланышы жок': 'unrelated',
};

export function normalizeRole(value: unknown): CauseRole | null {
  return ROLE_ALIASES[String(value ?? '').trim().toLowerCase().replace(/ё/g, 'е')] ?? null;
}

export type CauseFactor = { id: string; label: string; role: CauseRole; kind?: string; term?: 'short' | 'long'; explanation?: string };

export type CauseVerdict = CauseFactor & { chosen: CauseRole | null; correct: boolean };

export function normalizeFactors(raw: unknown): CauseFactor[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const factors: CauseFactor[] = [];
  raw.forEach((item, index) => {
    if (!item || typeof item !== 'object') return;
    const factor = item as Record<string, unknown>;
    const label = String(factor.label ?? '').trim();
    const role = normalizeRole(factor.role);
    if (!label || !role) return;
    let id = String(factor.id ?? '').trim() || `factor-${index + 1}`;
    while (seen.has(id)) id = `${id}-${index + 1}`;
    seen.add(id);
    factors.push({
      id, label, role,
      ...(typeof factor.kind === 'string' ? { kind: factor.kind } : {}),
      ...(factor.term === 'short' || factor.term === 'long' ? { term: factor.term } : {}),
      ...(typeof factor.explanation === 'string' ? { explanation: factor.explanation } : {}),
    });
  });
  return factors;
}

export function checkFactors(factors: CauseFactor[], chosen: Record<string, CauseRole | undefined>): CauseVerdict[] {
  return factors.map((factor) => ({ ...factor, chosen: chosen[factor.id] ?? null, correct: chosen[factor.id] === factor.role }));
}

/** Доля верно определённых ролей, 0–100; блок засчитан от 80. */
export function causeScore(verdicts: CauseVerdict[]): number {
  return verdicts.length ? Math.round((verdicts.filter((verdict) => verdict.correct).length / verdicts.length) * 100) : 0;
}

/** Позиции карточек схемы: причины и повод — слева, событие — в центре, последствия — справа. */
export function diagramLayout(chosen: Record<string, CauseRole | undefined>, ids: string[], width: number) {
  const narrow = width < 640;
  const column = narrow ? 0 : Math.max(220, width / 3);
  const left = ids.filter((id) => chosen[id] === 'cause' || chosen[id] === 'trigger');
  const right = ids.filter((id) => chosen[id] === 'consequence');
  const positions: Record<string, { x: number; y: number }> = {};
  if (narrow) {
    // Узкий экран: сверху вниз — причины, событие, последствия.
    let y = 0;
    left.forEach((id) => { positions[id] = { x: 0, y }; y += 90; });
    positions.event = { x: 0, y: y + 20 };
    y += 130;
    right.forEach((id) => { positions[id] = { x: 0, y }; y += 90; });
    return { positions, height: Math.max(260, y + 40) };
  }
  const rows = Math.max(left.length, right.length, 1);
  left.forEach((id, index) => { positions[id] = { x: 0, y: index * 96 }; });
  right.forEach((id, index) => { positions[id] = { x: column * 2, y: index * 96 }; });
  positions.event = { x: column, y: ((rows - 1) * 96) / 2 };
  return { positions, height: Math.max(260, rows * 96 + 80) };
}
