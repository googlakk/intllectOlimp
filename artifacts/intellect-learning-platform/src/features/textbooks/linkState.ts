import type { TextbookLinksOverview } from '@/lib/api/textbooks';

type TopicRow = TextbookLinksOverview['topics'][number];
export type LinkState = 'confirmed' | 'suggested' | 'covered' | 'rejected' | 'none';

/** Состояние темы: подтверждено / предложено / по пройденным темам / не найдено. */
export function topicLinkState(topic: TopicRow): LinkState {
  if (topic.links.some((link) => link.status === 'confirmed')) return 'confirmed';
  if (topic.links.length) return 'suggested';
  if (topic.rejected) return 'rejected';
  return topic.uses_covered_topics ? 'covered' : 'none';
}

export function linkSummary(topics: TopicRow[]): Record<LinkState, number> {
  const summary: Record<LinkState, number> = { confirmed: 0, suggested: 0, covered: 0, rejected: 0, none: 0 };
  topics.forEach((topic) => { summary[topicLinkState(topic)] += 1; });
  return summary;
}
