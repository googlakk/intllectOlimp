export async function runCredentialBatches<T, R>(
  items: T[],
  send: (batch: T[], offset: number) => Promise<R>,
  receive: (result: R, completed: number, offset: number) => void,
): Promise<void> {
  // Small requests stay below the proxy timeout. Completed batches are delivered
  // immediately; a later connection failure must not lose issued credentials.
  for (let offset = 0; offset < items.length; offset += 3) {
    const batch = items.slice(offset, offset + 3);
    const result = await send(batch, offset);
    receive(result, offset + batch.length, offset);
  }
}

export function credentialsCsv(items: Array<{ display_name?: string; login: string; temporary_password: string }>): string {
  const cell = (value: string) => {
    const safe = /^[\s]*[=+\-@]/.test(value) ? `'${value}` : value;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  return '\uFEFF' + [['Ученик', 'Логин', 'Временный пароль'], ...items.map(item =>
    [item.display_name || '', item.login, item.temporary_password])].map(row => row.map(cell).join(';')).join('\r\n');
}
