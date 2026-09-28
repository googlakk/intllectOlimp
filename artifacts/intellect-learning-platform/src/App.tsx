import { lazy, Suspense, useEffect, type ComponentType } from 'react';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '@/components/auth/AuthContext';
import { Shell } from '@/components/layout/Shell';

const Login = lazy(() => import('@/pages/Login'));
const GardenLesson = lazy(() => import('@/features/visualLesson/GardenLesson'));
const SampleLesson = lazy(() => import('@/features/visualLesson/SampleLesson'));
const ChangePassword = lazy(() => import('@/pages/ChangePassword'));
const AccessDenied = lazy(() => import('@/pages/AccessDenied'));
const Learn = lazy(() => import('@/pages/student/Learn'));
const SubjectView = lazy(() => import('@/pages/student/Subject'));
const Lesson = lazy(() => import('@/pages/student/Lesson'));
const Progress = lazy(() => import('@/pages/student/Progress'));
const Dashboard = lazy(() => import('@/pages/teacher/Dashboard'));
const Lessons = lazy(() => import('@/pages/teacher/Lessons'));
const LessonEditor = lazy(() => import('@/pages/teacher/LessonEditor'));
const LessonPresenter = lazy(() => import('@/pages/teacher/LessonPresenter'));
const Components = lazy(() => import('@/pages/teacher/Components'));
const Textbooks = lazy(() => import('@/pages/teacher/Textbooks'));
const Accounts = lazy(() => import('@/pages/teacher/Accounts'));
const Feedback = lazy(() => import('@/pages/admin/Feedback'));

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

function homeForRole(role: 'admin' | 'teacher' | 'student') {
  return role === 'student' ? '/learn' : role === 'admin' ? '/admin/accounts' : '/dashboard';
}

function ProtectedRoute({ component: Component, allowedRoles, allowPasswordChange = false }: { component: ComponentType, allowedRoles: string[], allowPasswordChange?: boolean }) {
  const { user, isLoading } = useAuth();
  const [, setLocation] = useLocation();
  const redirectTo = isLoading && !user ? null : !user
    ? '/'
    : user.must_change_password && !allowPasswordChange
      ? '/change-password'
      : !allowedRoles.includes(user.role)
        ? '/forbidden'
      : null;

  useEffect(() => {
    if (redirectTo) setLocation(redirectTo);
  }, [redirectTo, setLocation]);

  if (redirectTo || (isLoading && !user)) return null;
  
  return <Component />;
}

function RoutedPage({ component: Component, allowedRoles }: { component: ComponentType, allowedRoles: string[] }) {
  return (
    <Shell>
      <Suspense fallback={<PageLoader />}>
        <ProtectedRoute component={Component} allowedRoles={allowedRoles} />
      </Suspense>
    </Shell>
  );
}

function Router() {
  return (
    <Switch>
      <Route path="/visual/density" component={() => <Suspense fallback={<PageLoader />}><SampleLesson kind="density" /></Suspense>} />
      <Route path="/visual/silk-road" component={() => <Suspense fallback={<PageLoader />}><SampleLesson kind="silk-road" /></Suspense>} />
      <Route path="/visual/square-roots" component={() => <Suspense fallback={<PageLoader />}><GardenLesson /></Suspense>} />
      <Route path="/" component={() => <Suspense fallback={<PageLoader />}><Login /></Suspense>} />
      <Route path="/change-password" component={() => <Suspense fallback={<PageLoader />}><ProtectedRoute component={ChangePassword} allowedRoles={['admin', 'teacher', 'student']} allowPasswordChange /></Suspense>} />
      <Route path="/forbidden" component={() => <Suspense fallback={<PageLoader />}><ProtectedRoute component={AccessDenied} allowedRoles={['admin', 'teacher', 'student']} /></Suspense>} />
      
      <Route path="/learn" component={() => <RoutedPage component={Learn} allowedRoles={['student']} />} />
      <Route path="/learn/:subjectId" component={() => <RoutedPage component={SubjectView} allowedRoles={['student']} />} />
      <Route path="/learn/:subjectId/:topicId" component={() => <RoutedPage component={Lesson} allowedRoles={['student']} />} />
      <Route path="/progress" component={() => <RoutedPage component={Progress} allowedRoles={['student']} />} />
      
      <Route path="/dashboard" component={() => <RoutedPage component={Dashboard} allowedRoles={['teacher', 'admin']} />} />
      <Route path="/dashboard/students" component={() => <RoutedPage component={Accounts} allowedRoles={['teacher', 'admin']} />} />
      <Route path="/dashboard/lessons" component={() => <RoutedPage component={Lessons} allowedRoles={['teacher', 'admin']} />} />
      <Route path="/dashboard/lessons/:topicId" component={() => <RoutedPage component={LessonEditor} allowedRoles={['teacher', 'admin']} />} />
      <Route path="/dashboard/lessons/:topicId/present" component={() => <RoutedPage component={LessonPresenter} allowedRoles={['teacher', 'admin']} />} />
      <Route path="/dashboard/components" component={() => <RoutedPage component={Components} allowedRoles={['teacher', 'admin']} />} />
      <Route path="/dashboard/textbooks" component={() => <RoutedPage component={Textbooks} allowedRoles={['teacher', 'admin']} />} />
      <Route path="/admin/accounts" component={() => <RoutedPage component={Accounts} allowedRoles={['admin']} />} />
      <Route path="/admin/feedback" component={() => <RoutedPage component={Feedback} allowedRoles={['admin']} />} />
      
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
