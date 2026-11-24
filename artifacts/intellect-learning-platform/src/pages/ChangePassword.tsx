import { FormEvent, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useLocation } from 'wouter';
import { Loader2 } from 'lucide-react';
import { changePasswordRequest } from '@/lib/api';
import { homePath, useAuth } from '@/components/auth/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const MIN_LENGTH = 8;

export default function ChangePassword() {
  const { user, setUser, logout } = useAuth();
  const [, setLocation] = useLocation();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: changePasswordRequest,
    onSuccess: (updated) => {
      setUser(updated);
      setLocation(homePath(updated.role));
    },
  });

  if (!user) {
    setLocation('/');
    return null;
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (next.length < MIN_LENGTH) return setLocalError(`Новый пароль должен быть не короче ${MIN_LENGTH} символов`);
    if (next !== repeat) return setLocalError('Пароли не совпадают');
    setLocalError(null);
    mutation.mutate({ current_password: current, new_password: next });
  };

  const error = localError ?? (mutation.isError ? mutation.error.message : null);

  return (
    <div className="min-h-[100dvh] w-full flex items-center justify-center bg-muted/30 p-4">
      <form onSubmit={onSubmit} className="w-full max-w-md bg-card rounded-3xl shadow-xl border border-border p-6 md:p-8 space-y-5">
        <div>
          <h1 className="text-xl font-bold text-foreground">Смена пароля</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {user.must_change_password
              ? 'Вы вошли с временным паролем. Придумайте свой, чтобы продолжить.'
              : 'Введите текущий пароль и новый.'}
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="current">Текущий пароль</Label>
          <Input id="current" type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="next">Новый пароль</Label>
          <Input id="next" type="password" autoComplete="new-password" required value={next} onChange={(e) => setNext(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="repeat">Повторите новый пароль</Label>
          <Input id="repeat" type="password" autoComplete="new-password" required value={repeat} onChange={(e) => setRepeat(e.target.value)} />
        </div>
        {error && (
          <div role="alert" className="rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-sm font-medium text-destructive">{error}</div>
        )}
        <div className="flex gap-3">
          <Button type="submit" className="flex-1" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Сохранить
          </Button>
          {user.must_change_password ? (
            <Button type="button" variant="outline" onClick={() => logout()}>Выйти</Button>
          ) : (
            <Button type="button" variant="outline" onClick={() => setLocation(homePath(user.role))}>Отмена</Button>
          )}
        </div>
      </form>
    </div>
  );
}
