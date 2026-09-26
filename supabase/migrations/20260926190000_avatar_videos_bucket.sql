-- Закрытая корзина для видео аватара (в роликах может быть лицо учителя).
-- Файлы пишет только бэкенд (service role), ученик получает временную подписанную ссылку,
-- поэтому политики доступа для anon/authenticated не нужны.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('avatar-videos', 'avatar-videos', false, 104857600, array['video/mp4', 'video/webm']::text[])
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;
