import { FormEvent, useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useLocation } from 'wouter';
import { Loader2 } from 'lucide-react';
import { loginRequest } from '@/lib/api';
import { homePath, useAuth } from '@/components/auth/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export default function Login() {
  const { user, isLoading, setUser } = useAuth();
  const [, setLocation] = useLocation();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const mutation = useMutation({ mutationFn: loginRequest, onSuccess: setUser });

  useEffect(() => {
    if (user) setLocation(user.must_change_password ? '/change-password' : homePath(user.role));
  }, [user, setLocation]);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate({ login: login.trim(), password });
  };

  if (user || isLoading) return null;

  return (
    <div className="min-h-[100dvh] w-full flex items-center justify-center bg-muted/30 p-4">
      <div className="w-full max-w-md bg-card rounded-3xl shadow-xl border border-border overflow-hidden">
        <div className="p-8 text-center bg-gradient-to-b from-primary/5 to-transparent border-b border-border/50">
          <div className="w-16 h-16 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center text-3xl font-bold mx-auto mb-5 shadow-lg shadow-primary/30">
            И
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Добро пожаловать</h1>
          <p className="text-muted-foreground text-sm font-medium">Платформа для подготовки к олимпиадам</p>
        </div>

        <form onSubmit={onSubmit} className="p-6 md:p-8 space-y-5">
          <div className="space-y-2">
            <Label htmlFor="login">Логин</Label>
            <Input
              id="login"
              autoComplete="username"
              autoCapitalize="none"
              autoFocus
              required
              value={login}
              onChange={(event) => setLogin(event.target.value)}
              data-testid="input-login"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Пароль</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              data-testid="input-password"
            />
          </div>

          {mutation.isError && (
            <div role="alert" className="rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-sm font-medium text-destructive">
              {mutation.error.message}
            </div>
          )}

          <Button type="submit" className="w-full h-11" disabled={mutation.isPending} data-testid="button-login">
            {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Войти
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Логин и пароль выдаёт администратор школы или куратор.
          </p>
        </form>
      </div>
    </div>
  );
}
