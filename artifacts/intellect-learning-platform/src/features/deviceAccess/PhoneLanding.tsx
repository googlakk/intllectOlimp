import { useState } from 'react';
import { Check, Copy, Monitor, Smartphone } from 'lucide-react';

const PLATFORM_URL = 'https://inet.edu.kg';

export function PhoneLanding() {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'manual'>('idle');

  async function copyAddress() {
    try {
      await navigator.clipboard.writeText(PLATFORM_URL);
      setCopyState('copied');
    } catch {
      setCopyState('manual');
    }
  }

  return (
    <div className="min-h-[100dvh] bg-[#f7f8fc] text-slate-900 [background-image:radial-gradient(ellipse_at_50%_0%,#e9e7ff_0%,transparent_60%)]">
      <div className="mx-auto flex min-h-[100dvh] w-full max-w-md flex-col px-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1.5rem,env(safe-area-inset-top))]">
        <header className="flex items-center gap-2.5">
          <span aria-hidden="true" className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-xl font-bold text-white">И</span>
          <span className="text-lg font-bold tracking-tight">Интеллект</span>
        </header>

        <main className="flex flex-1 flex-col justify-center py-10">
          <div aria-hidden="true" className="relative mb-7 grid h-24 w-24 place-items-center rounded-[28px] border border-white bg-white/70 shadow-[0_12px_36px_-16px_#6366f1]">
            <Smartphone className="h-12 w-12 stroke-[1.5] text-indigo-600" />
            <span className="absolute -bottom-1 -right-1 grid h-9 w-9 place-items-center rounded-full border-4 border-[#f7f8fc] bg-indigo-100"><span className="h-2 w-2 rounded-full bg-indigo-500" /></span>
          </div>
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.14em] text-indigo-600">Скоро на телефоне</p>
          <h1 className="text-[32px] font-bold leading-[1.15] tracking-[-0.035em]">Мобильное приложение в разработке</h1>
          <p className="mt-4 text-base leading-relaxed text-slate-600">Готовим удобный формат для учёбы со смартфона. А пока приглашаем в Интеллект с компьютера или ноутбука.</p>

          <section aria-labelledby="desktop-access-title" className="mt-8 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2.5">
              <Monitor aria-hidden="true" className="h-5 w-5 shrink-0 text-indigo-600" />
              <h2 id="desktop-access-title" className="text-base font-bold">Продолжайте на компьютере</h2>
            </div>
            <p className="text-sm leading-relaxed text-slate-600">Все уроки, задания и результаты доступны в полной версии сайта.</p>
            <label className="mt-5 block text-xs font-medium text-slate-500" htmlFor="desktop-site-address">Адрес сайта</label>
            <input id="desktop-site-address" readOnly value={PLATFORM_URL} onFocus={event => event.currentTarget.select()} className="mt-1.5 h-12 w-full min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 text-base font-semibold text-slate-900 outline-none focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500/20" />
            <button type="button" onClick={copyAddress} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3 py-3 text-sm font-semibold text-white hover:bg-indigo-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2">
              {copyState === 'copied' ? <Check aria-hidden="true" className="h-4 w-4" /> : <Copy aria-hidden="true" className="h-4 w-4" />}
              {copyState === 'copied' ? 'Адрес скопирован' : 'Скопировать адрес сайта'}
            </button>
            <p role="status" className="mt-3 text-xs leading-relaxed text-slate-500">
              {copyState === 'manual' ? 'Нажмите на адрес выше, чтобы выделить и скопировать его вручную.' : copyState === 'copied' ? 'Откройте этот адрес в браузере на компьютере.' : 'Войдите с логином и паролем, выданными школой.'}
            </p>
          </section>
        </main>

        <footer className="text-xs leading-relaxed text-slate-500">Спасибо за терпение. Делаем учёбу удобнее.</footer>
      </div>
    </div>
  );
}
