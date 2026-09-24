import { useState } from 'react';
import { KeyRound, Loader2 } from 'lucide-react';
import { useLocation } from 'wouter';

import { useAuth } from '@/components/auth/AuthContext';

export default function ChangePassword() {
  const { user, changePassword } = useAuth();
  const [, setLocation] = useLocation();
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (password !== confirmation) return setError('Пароли не совпадают.');
    setError('');
    setPending(true);
    try {
      await changePassword(password);
      setLocation(user?.role === 'student' ? '/learn' : user?.role === 'admin' ? '/admin/accounts' : '/dashboard');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось изменить пароль.');
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="grid min-h-[100dvh] place-items-center bg-muted/30 p-4">
      <section className="w-full max-w-md rounded-lg border bg-card p-7 shadow-lg">
        <KeyRound className="mb-5 h-9 w-9 text-primary" />
        <h1 className="text-2xl font-bold">Создайте постоянный пароль</h1>
        <p className="mt-2 text-sm text-muted-foreground">Временный пароль больше не будет действовать после сохранения нового.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block space-y-2 text-sm font-semibold">
            <span>Новый пароль</span>
            <input type="password" autoComplete="new-password" minLength={10} required value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 w-full rounded-md border bg-background px-3" />
          </label>
          <label className="block space-y-2 text-sm font-semibold">
            <span>Повторите пароль</span>
            <input type="password" autoComplete="new-password" minLength={10} required value={confirmation} onChange={(e) => setConfirmation(e.target.value)} className="h-11 w-full rounded-md border bg-background px-3" />
          </label>
          <p className="text-xs text-muted-foreground">Не менее 10 символов, включая буквы и цифры.</p>
          {error && <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <button disabled={pending} className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary font-semibold text-primary-foreground disabled:opacity-60">
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            Сохранить пароль
          </button>
        </form>
      </section>
    </main>
  );
}
