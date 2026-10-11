export function PasswordChoice({ manual, password, onManual, onPassword, disabled = false }: {
  manual: boolean; password: string; onManual: (manual: boolean) => void;
  onPassword: (password: string) => void; disabled?: boolean;
}) {
  return <fieldset disabled={disabled} className="space-y-3 rounded-lg border p-4">
    <legend className="px-1 text-sm font-semibold">Временный пароль</legend>
    <label className="flex items-start gap-2 text-sm"><input type="radio" checked={!manual} onChange={() => onManual(false)} className="mt-1" />Сформировать отдельный простой пароль для каждого ученика</label>
    <label className="flex items-start gap-2 text-sm"><input type="radio" checked={manual} onChange={() => onManual(true)} className="mt-1" />Задать свой пароль</label>
    {manual && <label className="block text-sm">Пароль для выбранных учеников<input aria-label="Новый временный пароль" type="text" autoComplete="off" required minLength={6} maxLength={128} pattern="\S{6,128}" value={password} onChange={event => onPassword(event.target.value)} className="mt-2 h-11 w-full rounded-md border bg-background px-3" /><span className="mt-1 block text-xs text-muted-foreground">Не менее 6 символов без пробелов. Можно использовать простой пароль из букв или цифр.</span></label>}
    <p className="text-xs text-muted-foreground">При первом входе ученик задаст свой постоянный пароль.</p>
  </fieldset>;
}
