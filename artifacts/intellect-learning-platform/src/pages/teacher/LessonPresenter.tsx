import { useParams } from 'wouter';
import PresenterView from '@/features/lessonPresenter/PresenterView';

export default function LessonPresenter() {
  const { topicId } = useParams();
  return <PresenterView key={topicId} topicId={Number(topicId)} />;
}
