import { lazy, Suspense, useEffect, type ComponentType } from 'react';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '@/components/auth/AuthContext';
import { Shell } from '@/components/layout/Shell';

const Login = lazy(() => import('@/pages/Login'));
const Learn = lazy(() => import('@/pages/student/Learn'));
const SubjectView = lazy(() => import('@/pages/student/Subject'));
const Lesson = lazy(() => import('@/pages/student/Lesson'));
const Progress = lazy(() => import('@/pages/student/Progress'));
const Dashboard = lazy(() => import('@/pages/teacher/Dashboard'));
const Lessons = lazy(() => import('@/pages/teacher/Lessons'));
const LessonEditor = lazy(() => import('@/pages/teacher/LessonEditor'));
const Components = lazy(() => import('@/pages/teacher/Components'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function PageLoader() {
  return (
    <div className="flex min-h-[320px] items-center justify-center text-sm font-semibold text-muted-foreground">
      Загрузка...
    </div>
  );
}

function ProtectedRoute({ component: Component, allowedRole }: { component: ComponentType, allowedRole: string }) {
  const { user } = useAuth();
  const [, setLocation] = useLocation();
  const redirectTo = !user
    ? '/'
    : user.role !== allowedRole
      ? (user.role === 'student' ? '/learn' : '/dashboard')
      : null;

  useEffect(() => {
    if (redirectTo) setLocation(redirectTo);
  }, [redirectTo, setLocation]);

  if (redirectTo) return null;
  
  return <Component />;
}

function RoutedPage({ component: Component, allowedRole }: { component: ComponentType, allowedRole: string }) {
  return (
    <Shell>
      <Suspense fallback={<PageLoader />}>
        <ProtectedRoute component={Component} allowedRole={allowedRole} />
      </Suspense>
    </Shell>
  );
}

function Router() {
  return (
    <Switch>
      <Route path="/" component={() => <Suspense fallback={<PageLoader />}><Login /></Suspense>} />
      
      <Route path="/learn" component={() => <RoutedPage component={Learn} allowedRole="student" />} />
      <Route path="/learn/:subjectId" component={() => <RoutedPage component={SubjectView} allowedRole="student" />} />
      <Route path="/learn/:subjectId/:topicId" component={() => <RoutedPage component={Lesson} allowedRole="student" />} />
      <Route path="/progress" component={() => <RoutedPage component={Progress} allowedRole="student" />} />
      
      <Route path="/dashboard" component={() => <RoutedPage component={Dashboard} allowedRole="teacher" />} />
      <Route path="/dashboard/lessons" component={() => <RoutedPage component={Lessons} allowedRole="teacher" />} />
      <Route path="/dashboard/lessons/:topicId" component={() => <RoutedPage component={LessonEditor} allowedRole="teacher" />} />
      <Route path="/dashboard/components" component={() => <RoutedPage component={Components} allowedRole="teacher" />} />
      
      <Route>
        <div className="flex min-h-[100dvh] items-center justify-center bg-background">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-foreground mb-4">404</h1>
            <p className="text-muted-foreground font-medium">Страница не найдена</p>
          </div>
        </div>
      </Route>
    </Switch>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
