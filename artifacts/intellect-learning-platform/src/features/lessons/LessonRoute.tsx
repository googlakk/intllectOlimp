import { useParams } from 'wouter';
import { useAuth } from '@/components/auth/AuthContext';
import { useStudentLessonData } from './lessonManifest';
import { AssessmentExperience } from './AssessmentExperience';
import { RegularLesson } from './RegularLesson';

export function LessonRoute() {
  const { subjectId, topicId } = useParams();
  const { user } = useAuth();
  const data = useStudentLessonData(Number(topicId), user?.id);
  if (data.lesson?.lesson_metadata?.lesson_type === 'assessment' && user) {
    return <AssessmentExperience key={`${topicId}-${data.lesson.active_version_id}`} lesson={data.lesson} progress={data.progress} studentId={user.id} subjectId={subjectId ?? ''} reload={data.refetch} />;
  }
  return <RegularLesson key={topicId} />;
}
