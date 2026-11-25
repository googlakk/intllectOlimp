import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { AuthProvider, homePath, useAuth } from '@/components/auth/AuthContext';
import { ApiError, type Role } from '@/lib/api';
import { Shell } from '@/components/layout/Shell';

import Login from '@/pages/Login';
import ChangePassword from '@/pages/ChangePassword';
import AdminHome from '@/pages/admin/Home';
import Classes from '@/pages/admin/Classes';
import Learn from '@/pages/student/Learn';
import SubjectView from '@/pages/student/Subject';
import Lesson from '@/pages/student/Lesson';
import Progress from '@/pages/student/Progress';
import Dashboard from '@/pages/teacher/Dashboard';
import Lessons from '@/pages/teacher/Lessons';
import LessonEditor from '@/pages/teacher/LessonEditor';
import Components from '@/pages/teacher/Components';

const queryClient: QueryClient = new QueryClient({
  // A 401 from any request means the session ended: drop the cached user so
  // routes send the person back to the login page.
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (error instanceof ApiError && error.status === 401 && query.queryKey[0] !== 'auth') {
        queryClient.setQueryData(['auth', 'me'], null);
      }
    },
  }),
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function ProtectedRoute({ component: Component, allowedRoles }: { component: React.ComponentType, allowedRoles: Role[] }) {
  const { user, isLoading } = useAuth();
  const [, setLocation] = useLocation();
  const target = !user
    ? '/'
    : user.must_change_password
      ? '/change-password'
      : !allowedRoles.includes(user.role)
        ? homePath(user.role)
        : null;

  useEffect(() => {
    if (!isLoading && target) setLocation(target);
  }, [isLoading, target, setLocation]);

  if (isLoading || target) return null;
  return <Component />;
}

function Router() {
  return (
    <Switch>
      <Route path="/" component={Login} />
      <Route path="/change-password" component={ChangePassword} />
      <Route path="/admin" component={() => <Shell><ProtectedRoute component={AdminHome} allowedRoles={['admin']} /></Shell>} />
      <Route path="/admin/classes" component={() => <Shell><ProtectedRoute component={Classes} allowedRoles={['admin']} /></Shell>} />
      
      <Route path="/learn" component={() => <Shell><ProtectedRoute component={Learn} allowedRoles={['student']} /></Shell>} />
      <Route path="/learn/:subjectId" component={() => <Shell><ProtectedRoute component={SubjectView} allowedRoles={['student']} /></Shell>} />
      <Route path="/learn/:subjectId/:topicId" component={() => <Shell><ProtectedRoute component={Lesson} allowedRoles={['student']} /></Shell>} />
      <Route path="/progress" component={() => <Shell><ProtectedRoute component={Progress} allowedRoles={['student']} /></Shell>} />
      
      <Route path="/dashboard" component={() => <Shell><ProtectedRoute component={Dashboard} allowedRoles={['teacher', 'admin']} /></Shell>} />
      <Route path="/dashboard/lessons" component={() => <Shell><ProtectedRoute component={Lessons} allowedRoles={['teacher', 'admin']} /></Shell>} />
      <Route path="/dashboard/lessons/:topicId" component={() => <Shell><ProtectedRoute component={LessonEditor} allowedRoles={['teacher', 'admin']} /></Shell>} />
      <Route path="/dashboard/components" component={() => <Shell><ProtectedRoute component={Components} allowedRoles={['teacher', 'admin']} /></Shell>} />
      
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
