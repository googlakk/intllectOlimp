export function lessonProgressQueryKey(studentId: number, topicId: number) {
  return ['progress', studentId, topicId] as const;
}

export function completedLessonInvalidationKeys() {
  return [
    ['dashboard-overview'] as const,
    ['dashboard-students'] as const,
    ['subjects'] as const,
  ];
}
