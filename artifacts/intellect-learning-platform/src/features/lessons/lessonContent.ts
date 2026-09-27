const LITERAL_NEWLINE = /\\n(?!(?:eq|e|eg|abla|ot|otin|u|leq|geq|mid|parallel|exists|subseteq|supseteq|sim|cong|ewline)(?![a-zA-Z]))/g;
const PROTECTED_CONTENT = /(```[\s\S]*?```|`[^`]*`|\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/g;

function normalizePlainSegment(value: string): string {
  return value
    .replace(/\\\[([\s\S]*?)\\\]/g, (_match, math: string) => `$$${math}$$`)
    .replace(/\\\(([^\n]*?)\\\)/g, (_match, math: string) => `$${math}$`)
    .replace(/(^|[\s:;,])sqrt\s*\(([^()\n]+)\)/gi, (_match, prefix: string, radicand: string) => `${prefix}$\\sqrt{${radicand.trim()}}$`)
    .replace(/(^|[\s:;,])√\s*\(?\s*([+-]?[\d.,]+)\s*\)?/g, (_match, prefix: string, radicand: string) => `${prefix}$\\sqrt{${radicand}}$`)
    .replace(/(^|[\s:;,])(\\sqrt\s*\{[^{}]+\})/g, (_match, prefix: string, math: string) => `${prefix}$${math}$`)
    .replace(/(^|[\s:;,])(\\frac\s*\{[^{}]+\}\s*\{[^{}]+\})/g, (_match, prefix: string, math: string) => `${prefix}$${math}$`)
    .replace(/(^|[\s:;,])([A-Za-zА-Яа-яЁё\d)]+\s*\^[{]?[+-]?\d+[}]?)/g, (_match, prefix: string, math: string) => `${prefix}$${math}$`);
}

/** Repairs common AI notation while preserving code and already-delimited math. */
export function normalizeLessonMarkup(value: string): string {
  if (!value) return '';
  const normalized = value
    .replace(/\r\n?/g, '\n')
    // «\n» от модели — перевод строки, но не начало команды LaTeX: \neq, \ne, \neg, \nabla, \not, \nu…
    // Иначе «x \neq 0» превращалось в «x», новую строку и «eq0».
    .replace(LITERAL_NEWLINE, '\n')
    .replace(/\u00a0/g, ' ');
  const parts = normalized.split(PROTECTED_CONTENT);
  const repaired = parts.map((part, index) => index % 2 === 1 ? part : normalizePlainSegment(part)).join('');
  const boldMarkers = (repaired.match(/(?<!\\)\*\*/g) || []).length;
  return boldMarkers % 2 === 1 ? `${repaired}**` : repaired;
}

function verbalizeMath(value: string): string {
  return value
    .replace(/\\dfrac|\\tfrac/g, '\\frac')
    .replace(/\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}/g, 'дробь $1, делённая на $2')
    .replace(/\\sqrt\s*\[3\]\s*\{([^{}]+)\}/g, 'кубический корень из $1')
    .replace(/\\sqrt\s*\{([^{}]+)\}/g, 'квадратный корень из $1')
    .replace(/sqrt\s*\(([^()]+)\)/gi, 'квадратный корень из $1')
    .replace(/√\s*\(?\s*([^),.;]+)\s*\)?/g, 'квадратный корень из $1')
    .replace(/\^\s*\{?2\}?/g, ' в квадрате')
    .replace(/\^\s*\{?3\}?/g, ' в кубе')
    .replace(/\^\s*\{?([^{}\s]+)\}?/g, ' в степени $1')
    .replace(/\\times|\\cdot|×|·/g, ' умножить на ')
    .replace(/\\div|÷/g, ' разделить на ')
    .replace(/\\pm|±/g, ' плюс-минус ')
    .replace(/\\geq?|≥/g, ' больше или равно ')
    .replace(/\\leq?|≤/g, ' меньше или равно ')
    .replace(/\\neq|≠/g, ' не равно ')
    .replace(/=/g, ' равно ')
    .replace(/\+/g, ' плюс ')
    .replace(/(^|\s)-(?=\s|\d)/g, '$1 минус ')
    .replace(/[{}()[\]]/g, ' ')
    .replace(/\\(?:left|right|mathrm|text|operatorname)/g, ' ')
    .replace(/\\[A-Za-z]+/g, ' ');
}

/** Converts authored Markdown/LaTeX into text suitable for Russian TTS. */
export function narrationSpeechText(value: string): string {
  if (!value) return '';
  return verbalizeMath(value)
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/\$+/g, ' ')
    .replace(/\*\*|__|~~/g, ' ')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+[.)]\s+/gm, '')
    .replace(/\|/g, '. ')
    .replace(/[<>*_#]/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

export function narrationSegments(value: string, maxLength = 260): string[] {
  const text = narrationSpeechText(value);
  if (!text) return [];
  const sentences = text.match(/[^.!?…]+[.!?…]?/g)?.map((part) => part.trim()).filter(Boolean) || [text];
  const result: string[] = [];
  for (const sentence of sentences) {
    if (sentence.length <= maxLength) {
      result.push(sentence);
      continue;
    }
    const clauses = sentence.split(/(?<=[,;:])\s+/);
    let current = '';
    for (const clause of clauses) {
      if (clause.length > maxLength) {
        if (current) result.push(current);
        current = '';
        const words = clause.split(/\s+/);
        let wordChunk = '';
        for (const word of words) {
          if (!wordChunk || `${wordChunk} ${word}`.length <= maxLength) {
            wordChunk = wordChunk ? `${wordChunk} ${word}` : word;
          } else {
            result.push(wordChunk);
            wordChunk = word;
          }
        }
        current = wordChunk;
      } else if (!current || `${current} ${clause}`.length <= maxLength) {
        current = current ? `${current} ${clause}` : clause;
      } else {
        result.push(current);
        current = clause;
      }
    }
    if (current) result.push(current);
  }
  return result;
}
