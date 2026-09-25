-- Решение учителя «этот параграф теме не подходит» сохраняется как rejected:
-- повторный подбор параграфов его не отменяет. Применяется после согласования владельцем.
ALTER TABLE public.topic_textbook_links DROP CONSTRAINT IF EXISTS topic_textbook_links_status_check;
ALTER TABLE public.topic_textbook_links
  ADD CONSTRAINT topic_textbook_links_status_check CHECK (status IN ('suggested', 'confirmed', 'rejected'));
