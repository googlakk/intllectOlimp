/**
 * Таймер бездействия: срабатывает один раз, если ученик долго ничего не делает.
 * Пока вкладка скрыта, время не идёт; любое действие начинает отсчёт заново.
 */
export class IdleTimer {
  private handle: ReturnType<typeof setTimeout> | null = null;
  private fired = false;

  constructor(private readonly delayMs: number, private readonly onIdle: () => void) {}

  /** Действие ученика или смена шага (fresh=true — на новом шаге можно сработать снова). */
  reset(fresh = false): void {
    if (fresh) this.fired = false;
    this.stop();
    if (!this.fired) {
      this.handle = setTimeout(() => {
        this.handle = null;
        this.fired = true;
        this.onIdle();
      }, this.delayMs);
    }
  }

  stop(): void {
    if (this.handle !== null) clearTimeout(this.handle);
    this.handle = null;
  }
}
