export type StudentCsvRow = { display_name: string; login: string };

function splitDelimitedLine(line: string, delimiter: string): string[] {
  const values: string[] = [];
  let value = '';
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"') {
      if (quoted && line[index + 1] === '"') {
        value += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === delimiter && !quoted) {
      values.push(value.trim());
      value = '';
    } else {
      value += character;
    }
  }
  values.push(value.trim());
  return values;
}

export function parseStudentCsv(source: string): StudentCsvRow[] {
  const lines = source.replace(/^\uFEFF/, '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  return lines.flatMap((line, index) => {
    const delimiter = line.includes(';') ? ';' : line.includes('\t') ? '\t' : ',';
    const [display_name = '', login = ''] = splitDelimitedLine(line, delimiter);
    const normalizedLogin = login.toLocaleLowerCase('ru');
    if (index === 0 && ['login', 'логин', 'username'].includes(normalizedLogin)) return [];
    return display_name && login ? [{ display_name, login }] : [];
  });
}
