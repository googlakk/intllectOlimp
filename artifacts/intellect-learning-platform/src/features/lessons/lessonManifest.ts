import { useStudentLessonManifest } from '@/lib/api';

export function useStudentLessonData(topicId: number, studentId?: number) {
  const manifest = useStudentLessonManifest(topicId, studentId, Boolean(studentId));
  return {
    lesson: manifest.data?.lesson,
    progress: manifest.data?.progress,
    isLoading: manifest.isLoading,
    error: manifest.error as Error | null,
    refetch: manifest.refetch,
  };
}
