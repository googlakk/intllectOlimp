import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '@/components/auth/AuthContext';
import { Shell } from '@/components/layout/Shell';

import Login from '@/pages/Login';
import Learn from '@/pages/student/Learn';
import SubjectView from '@/pages/student/Subject';
import Lesson from '@/pages/student/Lesson';
import Progress from '@/pages/student/Progress';
import Dashboard from '@/pages/teacher/Dashboard';
import Lessons from '@/pages/teacher/Lessons';
import LessonEditor from '@/pages/teacher/LessonEditor';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function ProtectedRoute({ component: Component, allowedRole }: { component: any, allowedRole: string }) {
  const { user } = useAuth();
  const [, setLocation] = useLocation();

  if (!user) {
    setLocation('/');
    return null;
  }
  
  if (user.role !== allowedRole) {
    setLocation(user.role === 'student' ? '/learn' : '/dashboard');
    return null;
  }
  
  return <Component />;
}

function Router() {
  return (
    <Switch>
      <Route path="/" component={Login} />
      
      <Route path="/learn" component={() => <Shell><ProtectedRoute component={Learn} allowedRole="student" /></Shell>} />
      <Route path="/learn/:subjectId" component={() => <Shell><ProtectedRoute component={SubjectView} allowedRole="student" /></Shell>} />
      <Route path="/learn/:subjectId/:topicId" component={() => <Shell><ProtectedRoute component={Lesson} allowedRole="student" /></Shell>} />
      <Route path="/progress" component={() => <Shell><ProtectedRoute component={Progress} allowedRole="student" /></Shell>} />
      
      <Route path="/dashboard" component={() => <Shell><ProtectedRoute component={Dashboard} allowedRole="teacher" /></Shell>} />
      <Route path="/dashboard/lessons" component={() => <Shell><ProtectedRoute component={Lessons} allowedRole="teacher" /></Shell>} />
      <Route path="/dashboard/lessons/:topicId" component={() => <Shell><ProtectedRoute component={LessonEditor} allowedRole="teacher" /></Shell>} />
      
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
