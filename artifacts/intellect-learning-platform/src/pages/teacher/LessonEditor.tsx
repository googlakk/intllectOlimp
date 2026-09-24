import { useParams } from 'wouter';
import EditorWorkspace from '@/features/lessonEditor/EditorWorkspace';

export default function LessonEditor() {
  const { topicId } = useParams();
  return <EditorWorkspace key={topicId} topicId={Number(topicId)} />;
}
