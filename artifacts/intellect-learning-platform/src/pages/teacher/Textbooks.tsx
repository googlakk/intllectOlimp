import { useState } from 'react';
import { BookMarked } from 'lucide-react';
import { useTextbooks } from '@/lib/api';
import { TextbookUpload } from '@/features/textbooks/TextbookUpload';
import { StatusBadge, TextbookDetailView } from '@/features/textbooks/TextbookDetailView';

export default function Textbooks() {
  const { data: books, isLoading, isError } = useTextbooks();
  const [openId, setOpenId] = useState<number | null>(null);

  if (openId !== null) {
    return <div className="mx-auto max-w-6xl"><TextbookDetailView id={openId} onBack={() => setOpenId(null)} /></div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-bold"><BookMarked className="h-6 w-6 text-primary" aria-hidden /> Учебники</h1>
        <p className="text-muted-foreground">Уроки, тьютор и проверки опираются на учебник: определения, формулы и задачи — из книги, со ссылками на страницы.</p>
      </header>
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <section className="space-y-3" aria-label="Загруженные учебники">
          {isLoading && <p>Загружаем список…</p>}
          {isError && <p role="alert">Не удалось загрузить учебники.</p>}
          {books?.length === 0 && <p className="text-muted-foreground">Учебников пока нет — загрузите первый.</p>}
          {books?.map((book) => (
            <button key={book.id} type="button" onClick={() => setOpenId(book.id)}
              className="flex w-full flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 text-left hover:border-primary/40">
              <span>
                <span className="block font-semibold">{book.title}</span>
                <span className="text-sm text-muted-foreground">{book.grade} класс{book.page_count ? ` · ${book.page_count} стр.` : ''}</span>
              </span>
              <StatusBadge book={book} />
            </button>
          ))}
        </section>
        <TextbookUpload onDone={setOpenId} />
      </div>
    </div>
  );
}
