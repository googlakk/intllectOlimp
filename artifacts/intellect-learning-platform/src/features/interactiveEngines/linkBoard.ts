export const linkKey = (from: string, to: string) => `${from}->${to}`;

function seedFrom(text: string): number {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) hash = Math.imul(hash ^ text.charCodeAt(index), 16777619);
  return hash >>> 0;
}

/**
 * Стабильное перемешивание: одинаковое при каждом открытии блока, но порядок
 * на экране никогда не совпадает с правильным и не выдаёт ответ.
 */
export function boardOrder<T extends { id: string }>(items: T[]): T[] {
  if (items.length < 3) return [...items].reverse();
  let seed = seedFrom(items.map((item) => item.id).join('|'));
  const next = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 2 ** 32;
  };
  const shuffled = [...items];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(next() * (index + 1));
    [shuffled[index], shuffled[swap]] = [shuffled[swap], shuffled[index]];
  }
  const unchanged = shuffled.every((item, index) => item.id === items[index].id);
  return unchanged ? [...shuffled.slice(1), shuffled[0]] : shuffled;
}
