import { ReactNode } from 'react';
import { Link, useLocation } from 'wouter';
import { useAuth } from '@/components/auth/AuthContext';
import { LogOut, BookOpen, BarChart, LayoutDashboard, FileText, Blocks } from 'lucide-react';

export function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const [location] = useLocation();

  if (!user) return <>{children}</>;

  const NavLink = ({ href, icon: Icon, label }: { href: string, icon: any, label: string }) => {
    const isActive = location === href || (href !== '/learn' && href !== '/dashboard' && location.startsWith(href));
    return (
      <Link href={href} className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all duration-200 font-medium ${isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}>
        <Icon className="w-4 h-4" />
        <span>{label}</span>
      </Link>
    );
  };

  return (
    <div className="min-h-[100dvh] flex flex-col bg-background selection:bg-primary/20 selection:text-primary">
      <header className="h-16 border-b border-border/50 bg-card/80 backdrop-blur-xl px-4 md:px-6 flex items-center justify-between sticky top-0 z-50 transition-all shadow-sm">
        <div className="flex items-center gap-8">
          <Link href={user.role === 'student' ? '/learn' : '/dashboard'} className="flex items-center gap-2.5 text-foreground font-bold text-xl tracking-tight group">
            <div className="w-8 h-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center shadow-sm group-hover:scale-105 transition-transform">
              <span className="leading-none mt-0.5">И</span>
            </div>
            Интеллект
          </Link>
          <nav className="hidden md:flex items-center gap-1.5">
            {user.role === 'student' ? (
              <>
                <NavLink href="/learn" icon={BookOpen} label="Обучение" />
                <NavLink href="/progress" icon={BarChart} label="Мой прогресс" />
              </>
            ) : (
              <>
                <NavLink href="/dashboard" icon={LayoutDashboard} label="Обзор" />
                <NavLink href="/dashboard/lessons" icon={FileText} label="Уроки" />
                <NavLink href="/dashboard/components" icon={Blocks} label="Компоненты" />
              </>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden md:block text-sm text-right">
            <div className="font-semibold text-foreground leading-tight">{user.name}</div>
            <div className="text-muted-foreground text-xs font-medium">{user.role === 'student' ? `${user.grade} класс` : 'Преподаватель'}</div>
          </div>
          <button onClick={logout} className="p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive rounded-full transition-colors" title="Выйти">
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>
      
      {/* Mobile nav */}
      <div className="md:hidden border-b border-border/50 bg-card px-4 py-2 flex items-center gap-2 overflow-x-auto custom-scrollbar">
         {user.role === 'student' ? (
            <>
              <NavLink href="/learn" icon={BookOpen} label="Обучение" />
              <NavLink href="/progress" icon={BarChart} label="Прогресс" />
            </>
          ) : (
            <>
              <NavLink href="/dashboard" icon={LayoutDashboard} label="Обзор" />
              <NavLink href="/dashboard/lessons" icon={FileText} label="Уроки" />
              <NavLink href="/dashboard/components" icon={Blocks} label="Компоненты" />
            </>
          )}
      </div>

      <main className="flex-1 w-full max-w-6xl mx-auto p-4 md:p-8 animate-in fade-in duration-500">
        {children}
      </main>
    </div>
  );
}
