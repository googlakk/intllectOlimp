import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowLeft, Lightbulb, Loader2, MessageCircle, Send } from 'lucide-react';
import { parseMathText } from '@/components/blocks/ShortExplanation';
import { Drawer, DrawerContent, DrawerDescription, DrawerTitle } from '@/components/ui/drawer';
import type { LessonTutor } from './useLessonTutor';

const STUCK_MESSAGE = 'Не понимаю, что делать';

/** Окно помощника: разговор по текущему шагу урока. */
function TutorConversation({ tutor, autoFocus = false, onOpenTheory }: { tutor: LessonTutor; autoFocus?: boolean; onOpenTheory?: () => void }) {
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const { locked, pending, messages } = tutor;
  // Диктор читает только реплику, пришедшую сейчас (id «local-…»), а не восстановленный диалог
  // и не старые реплики при смене шага.
  const [announcement, setAnnouncement] = useState('');
  const announced = useRef(new Set<string>());

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
    const reply = messages.filter((message) => message.role === 'tutor' && message.id.startsWith('local-')
      && !announced.current.has(message.id)).at(-1);
    messages.forEach((message) => announced.current.add(message.id));
    if (!reply) return;
    // Сначала очищаем: одинаковая фраза подряд тоже должна прозвучать.
    setAnnouncement('');
    requestAnimationFrame(() => setAnnouncement(reply.text));
  }, [messages, pending]);

  useEffect(() => {
    if (autoFocus && !locked) inputRef.current?.focus({ preventScroll: true });
  }, [autoFocus, locked]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.trim() || pending) return;
    tutor.sendMessage(draft);
    setDraft('');
  };

  const checkMyIdea = () => {
    setDraft((current) => current || 'Я думаю так: ');
    inputRef.current?.focus();
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <p className="sr-only" aria-live="polite">{announcement}</p>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-2" aria-busy={pending}>
        {messages.length === 0 && !pending && (
          <p className="py-2 text-sm text-muted-foreground">
            {locked
              ? 'Это итоговое задание — здесь ты справляешься сам. Если что-то забыл, вернись к объяснению.'
              : 'Застрял? Попроси подсказку или напиши, что непонятно — разберём по шагам.'}
          </p>
        )}
        {messages.map((message) => (
          <div key={message.id} className={message.role === 'student' ? 'flex justify-end' : 'flex justify-start'}>
            <div
              className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                message.role === 'student' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
              }`}
            >
              {message.role === 'tutor' ? parseMathText(message.text) : message.text}
              {message.role === 'tutor' && (message.offer || typeof message.theoryStep === 'number') && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {message.offer && !locked && (
                    <button type="button" onClick={tutor.requestHint} disabled={pending}
                      className="min-h-[44px] rounded-lg border border-border bg-card px-3 text-xs font-semibold hover:bg-muted disabled:opacity-50">
                      Да, помоги
                    </button>
                  )}
                  {typeof message.theoryStep === 'number' && (
                    <button type="button" onClick={() => { tutor.openTheory(message.theoryStep as number); onOpenTheory?.(); }}
                      className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-border bg-card px-3 text-xs font-semibold hover:bg-muted">
                      <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> К объяснению
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        {pending && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden /> Помощник думает…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {!locked && (
        <div className="shrink-0 space-y-2 border-t border-border px-3 py-2">
          <div className="flex flex-wrap gap-1.5">
            <button type="button" onClick={tutor.requestHint} disabled={pending}
              className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-border px-2.5 text-xs font-semibold hover:bg-muted disabled:opacity-50">
              <Lightbulb className="h-3.5 w-3.5" aria-hidden /> Подсказка
            </button>
            <button type="button" onClick={() => tutor.sendMessage(STUCK_MESSAGE)} disabled={pending}
              className="min-h-[44px] rounded-lg border border-border px-2.5 text-xs font-semibold hover:bg-muted disabled:opacity-50">
              {STUCK_MESSAGE}
            </button>
            <button type="button" onClick={checkMyIdea} disabled={pending}
              className="min-h-[44px] rounded-lg border border-border px-2.5 text-xs font-semibold hover:bg-muted disabled:opacity-50">
              Проверь мою мысль
            </button>
          </div>
          <form onSubmit={submit} className="flex gap-2">
            <input
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={500}
              placeholder="Спроси помощника…"
              aria-label="Сообщение помощнику"
              className="min-h-[44px] min-w-0 flex-1 rounded-lg border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button type="submit" disabled={pending || !draft.trim()} aria-label="Отправить"
              className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground disabled:opacity-50">
              <Send className="h-4 w-4" aria-hidden />
            </button>
          </form>
        </div>
      )}
      <p className="shrink-0 px-3 pb-2 text-[11px] text-muted-foreground">Учитель может посмотреть этот диалог.</p>
    </div>
  );
}

/** Компьютер: карточка в правой колонке урока. */
export function TutorCard({ tutor }: { tutor: LessonTutor }) {
  const { hasOffer, seenOffer } = tutor;
  // Карточка на телефоне скрыта стилями, но смонтирована: там предложение показывает точка на кнопке.
  useEffect(() => {
    if (hasOffer && window.matchMedia('(min-width: 1024px)').matches) seenOffer();
  }, [hasOffer, seenOffer]);
  return (
    <section aria-label="Помощник" className="hidden min-h-[260px] flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-md lg:flex">
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-4 py-3">
        <MessageCircle className="h-4 w-4 text-primary" aria-hidden />
        <p className="text-sm font-bold text-foreground">Помощник</p>
      </div>
      <TutorConversation tutor={tutor} />
    </section>
  );
}

/** Телефон: кнопка открывает нижнюю панель. Предложение помощи панель само не открывает — только точка на кнопке. */
export function TutorMobileButton({ tutor }: { tutor: LessonTutor }) {
  const [open, setOpen] = useState(false);
  const { seenOffer } = tutor;
  useEffect(() => {
    if (open) seenOffer();
  }, [open, seenOffer, tutor.hasOffer]);
  return (
    <div className="lg:hidden">
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={tutor.hasOffer ? 'Помощник: есть предложение помочь' : 'Открыть помощника'}
        className="fixed bottom-[clamp(8rem,28vh,11rem)] left-2 z-[70] grid h-12 w-12 place-items-center rounded-full border border-border bg-card text-primary shadow-lg"
      >
        <MessageCircle className="h-5 w-5" aria-hidden />
        {tutor.hasOffer && <span className="absolute right-1 top-1 h-3 w-3 rounded-full bg-primary ring-2 ring-card" aria-hidden />}
      </button>
      <Drawer open={open} onOpenChange={setOpen} shouldScaleBackground={false}>
        <DrawerContent overlayClassName="z-[80]" className="z-[80] flex h-[75dvh] flex-col">
          <DrawerTitle className="px-4 pt-3 text-base font-bold">Помощник</DrawerTitle>
          <DrawerDescription className="sr-only">Разговор с помощником по текущему шагу урока</DrawerDescription>
          <TutorConversation tutor={tutor} autoFocus={open} onOpenTheory={() => setOpen(false)} />
        </DrawerContent>
      </Drawer>
    </div>
  );
}
