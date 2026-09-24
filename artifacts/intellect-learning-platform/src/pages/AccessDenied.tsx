import { ArrowLeft, ShieldX } from 'lucide-react';
import { Link } from 'wouter';

import { useAuth } from '@/components/auth/AuthContext';

export default function AccessDenied() {
  const { user } = useAuth();
  const home = user?.role === 'student' ? '/learn' : user?.role === 'admin' ? '/admin/accounts' : '/dashboard';

  return (
    <main className="grid min-h-[calc(100dvh-4rem)] place-items-center p-6">
      <section className="w-full max-w-md text-center">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-lg bg-destructive/10 text-destructive">
          <ShieldX className="h-7 w-7" />
        </div>
        <p className="mt-5 text-sm font-bold uppercase text-muted-foreground">Ошибка 403</p>
        <h1 className="mt-2 text-2xl font-bold">Нет доступа к этому разделу</h1>
        <p className="mt-3 text-muted-foreground">
          Вашему аккаунту не назначена роль или класс, необходимый для просмотра этой страницы.
        </p>
        <Link href={home} className="mt-6 inline-flex h-11 items-center gap-2 rounded-md bg-primary px-5 font-semibold text-primary-foreground">
          <ArrowLeft className="h-4 w-4" />
          Вернуться
        </Link>
      </section>
    </main>
  );
}
