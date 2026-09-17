import { useState, useEffect } from 'react';
import { useLoginUsers, useLogin } from '@/lib/api';
import { useAuth } from '@/components/auth/AuthContext';
import { useLocation } from 'wouter';
import { Loader2, User as UserIcon, GraduationCap, ArrowRight } from 'lucide-react';

export default function Login() {
  const { user, login } = useAuth();
  const [, setLocation] = useLocation();
  const [role, setRole] = useState<'student' | 'teacher'>('student');
  
  const { data: users, isLoading } = useLoginUsers();
  const loginMutation = useLogin();

  useEffect(() => {
    if (user) {
      setLocation(user.role === 'student' ? '/learn' : '/dashboard');
    }
  }, [user, setLocation]);

  const handleLogin = (name: string) => {
    loginMutation.mutate(
      { role, name },
      {
        onSuccess: (u) => {
          login(u);
        }
      }
    );
  };

  if (user) return null;

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
        
        <div className="p-6 md:p-8">
          <div className="flex p-1 bg-muted rounded-xl mb-6">
            <button 
              onClick={() => setRole('student')}
              className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all ${role === 'student' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
            >
              Ученик
            </button>
            <button 
              onClick={() => setRole('teacher')}
              className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all ${role === 'teacher' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
            >
              Преподаватель
            </button>
          </div>

          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="w-8 h-8 animate-spin mb-4 text-primary/50" />
              <p className="text-sm font-medium">Загрузка пользователей...</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
              {(role === 'student' ? users?.students : users?.teachers)?.map((u) => (
                <button
                  key={u.id}
                  disabled={loginMutation.isPending}
                  onClick={() => handleLogin(u.name)}
                  className="w-full flex items-center justify-between p-4 rounded-xl border border-transparent hover:border-primary/20 bg-muted/30 hover:bg-primary/5 transition-all text-left group disabled:opacity-50"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-card shadow-sm border border-border flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors">
                      {role === 'student' ? <GraduationCap className="w-5 h-5" /> : <UserIcon className="w-5 h-5" />}
                    </div>
                    <div>
                      <div className="font-semibold text-foreground">{u.name}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {role === 'student' ? `${u.grade} класс` : 'Доступ к платформе'}
                      </div>
                    </div>
                  </div>
                  <ArrowRight className="w-5 h-5 text-muted-foreground opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-primary" />
                </button>
              ))}
              
              {(role === 'student' ? users?.students : users?.teachers)?.length === 0 && (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  Пользователи не найдены.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
