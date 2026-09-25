import { useQuery } from '@tanstack/react-query';

import { request } from './client';

export type TextbookStatus =
  | 'uploaded' | 'extracting' | 'needs_ai' | 'recognizing' | 'structuring' | 'ready' | 'needs_review' | 'failed';

export type Textbook = {
  id: number;
  title: string;
  authors: string | null;
  year: number | null;
  grade: number;
  subject_id: number | null;
  language: 'ru' | 'ky';
  status: TextbookStatus;
  stalled: boolean;
  progress: { stage?: string; pages?: number; scans_left?: number; sections?: number; items_left?: number; calibration?: number };
  page_count: number | null;
  page_offset: number | null;
  student_display: 'refs_only' | 'verbatim';
  error: string | null;
  created_at: string | null;
};

export type TextbookSectionSummary = {
  id: number; number: string; title: string; chapter: string; printed_page: number | null;
  pdf_from: number; pdf_to: number; items_status: string; items: number;
};

export type TextbookDetail = { textbook: Textbook; pages_to_review: number[]; sections: TextbookSectionSummary[] };

export type TextbookPageView = {
  page_index: number; printed_page: number; text: string; source: 'text' | 'ocr' | 'edited';
  status: string; needs_review: boolean; uncertain: string[];
};

export type TextbookItemView = {
  id: number; kind: string; label: string; page: number | null; text: string; answer: string | null; difficulty: number | null;
};

export type TextbookSectionView = {
  section: Omit<TextbookSectionSummary, 'items'>;
  pages: TextbookPageView[];
  items: TextbookItemView[];
};

export type TextbookCreateInput = {
  title: string; grade: number; subject_id?: number | null; language: 'ru' | 'ky';
  authors?: string | null; year?: number | null; file_name: string; file_size: number;
};

const RUNNING: TextbookStatus[] = ['extracting', 'recognizing', 'structuring'];
export const isTextbookRunning = (book: Pick<Textbook, 'status' | 'stalled'>) => RUNNING.includes(book.status) && !book.stalled;

export const createTextbook = (input: TextbookCreateInput) =>
  request<{ textbook: Textbook; upload_url: string }>('/textbooks', { method: 'POST', body: JSON.stringify(input) });

export const processTextbook = (id: number) =>
  request<{ textbook: Textbook; started: boolean }>(`/textbooks/${id}/process`, { method: 'POST' });

export const MAX_TEXTBOOK_BYTES = 150 * 1024 * 1024;

/** Удалить запись, если файл не загрузился (сорвалась загрузка). */
export const deleteUnuploadedTextbook = (id: number) =>
  request<void>(`/textbooks/${id}`, { method: 'DELETE' }).catch(() => undefined);

export const updateTextbookPage = (id: number, pageIndex: number, text: string) =>
  request<TextbookPageView>(`/textbooks/${id}/pages/${pageIndex}`, { method: 'PUT', body: JSON.stringify({ text }) });

/** Файл уходит прямо в закрытое хранилище по разовой ссылке, минуя сервер (книги по 50–150 МБ). */
export function uploadTextbookFile(url: string, file: File, onProgress?: (share: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', url);
    xhr.setRequestHeader('Content-Type', 'application/pdf');
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress?.(event.loaded / event.total); };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Хранилище ответило ${xhr.status}`)));
    xhr.onerror = () => reject(new Error('Не удалось загрузить файл: проверьте соединение'));
    xhr.send(file);
  });
}

const POLL_MS = 4000;

export const useTextbooks = () =>
  useQuery({
    queryKey: ['textbooks'],
    queryFn: () => request<Textbook[]>('/textbooks'),
    // Пока какая-то книга обрабатывается — обновляем статус.
    refetchInterval: (query) => (query.state.data?.some(isTextbookRunning) ? POLL_MS : false),
  });

export const useTextbook = (id: number | null) =>
  useQuery({
    queryKey: ['textbook', id],
    queryFn: () => request<TextbookDetail>(`/textbooks/${id}`),
    enabled: id !== null,
    refetchInterval: (query) => (query.state.data && isTextbookRunning(query.state.data.textbook) ? POLL_MS : false),
  });

export const useTextbookSection = (id: number | null, sectionId: number | null) =>
  useQuery({
    queryKey: ['textbook-section', id, sectionId],
    queryFn: () => request<TextbookSectionView>(`/textbooks/${id}/sections/${sectionId}`),
    enabled: id !== null && sectionId !== null,
  });

export type TopicLink = {
  section_id: number; status: 'suggested' | 'confirmed'; source: 'ktp' | 'match' | 'model' | 'manual';
  role: 'primary' | 'supporting'; score: number | null; number: string; title: string;
};

export type TextbookLinksOverview = {
  sections: Array<{ id: number; number: string; title: string; chapter: string; printed_page: number | null }>;
  topics: Array<{ id: number; ktp_number: string | null; name: string; lesson_type: string; uses_covered_topics: boolean; rejected: boolean; links: TopicLink[] }>;
};

export const useTextbookLinks = (id: number | null, enabled = true) =>
  useQuery({
    queryKey: ['textbook-links', id],
    queryFn: () => request<TextbookLinksOverview>(`/textbooks/${id}/links`),
    enabled: enabled && id !== null,
    retry: false,
  });

export const suggestTextbookLinks = (id: number) =>
  request<{ confirmed: number; suggested: number; not_found: number; skipped: number }>(`/textbooks/${id}/links/suggest`, { method: 'POST' });

export const setTopicTextbookLinks = (id: number, topicId: number, sectionIds: number[]) =>
  request<{ topic_id: number; section_ids: number[] }>(`/textbooks/${id}/links/${topicId}`, {
    method: 'PUT', body: JSON.stringify({ section_ids: sectionIds }),
  });

export const setTextbookSubject = (id: number, subjectId: number) =>
  request<Textbook>(`/textbooks/${id}/subject`, { method: 'PUT', body: JSON.stringify({ subject_id: subjectId }) });

export const confirmSuggestedLinks = (id: number, topicIds: number[]) =>
  request<{ topics: number; links: number }>(`/textbooks/${id}/links/confirm`, { method: 'POST', body: JSON.stringify({ topic_ids: topicIds }) });
