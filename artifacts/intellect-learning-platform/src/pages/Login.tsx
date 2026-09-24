import { useEffect, useState } from 'react';
import { ArrowRight, Eye, EyeOff, Loader2, LockKeyhole, UserRound } from 'lucide-react';
import { useLocation } from 'wouter';

import { useAuth } from '@/components/auth/AuthContext';
import { takeAuthNotice } from '@/lib/authSession';

function homeFor(role: 'admin' | 'teacher' | 'student') {
  if (role === 'student') return '/learn';
  if (role === 'admin') return '/admin/accounts';
  return '/dashboard';
}

export default function Login() {
  const { user, isLoading, login } = useAuth();
  const [, setLocation] = useLocation();
  const [loginName, setLoginName] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(() => takeAuthNotice());

  useEffect(() => {
    if (user) setLocation(user.must_change_password ? '/change-password' : homeFor(user.role));
  }, [user, setLocation]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setPending(true);
    try {
      const signedIn = await login(loginName, password);
      setLocation(signedIn.must_change_password ? '/change-password' : homeFor(signedIn.role));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось войти.');
    } finally {
      setPending(false);
    }
  };

  if (user || isLoading) return null;

  return (
    <main className="grid min-h-[100dvh] place-items-center bg-muted/30 p-4">
      <section className="w-full max-w-sm overflow-hidden rounded-lg border bg-card shadow-lg">
        <header className="border-b px-7 py-7 text-center">
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-lg bg-primary text-2xl font-bold text-primary-foreground">И</div>
          <h1 className="text-2xl font-bold text-foreground">Вход в Интеллект</h1>
          <p className="mt-2 text-sm text-muted-foreground">Используйте данные, выданные школой</p>
        </header>
        <form onSubmit={submit} className="space-y-5 p-7">
          <label className="block space-y-2 text-sm font-semibold text-foreground">
            <span>Логин</span>
            <span className="relative block">
              <UserRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={loginName}
                onChange={(event) => setLoginName(event.target.value)}
                autoComplete="username"
                required
                minLength={3}
                className="h-11 w-full rounded-md border bg-background pl-10 pr-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
            </span>
          </label>
          <label className="block space-y-2 text-sm font-semibold text-foreground">
            <span>Пароль</span>
            <span className="relative block">
              <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                className="h-11 w-full rounded-md border bg-background pl-10 pr-10 outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center text-muted-foreground hover:text-foreground"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </span>
          </label>
          {error && <p role="alert" className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <button
            type="submit"
            disabled={pending}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            Войти
          </button>
        </form>
      </section>
    </main>
  );
}
