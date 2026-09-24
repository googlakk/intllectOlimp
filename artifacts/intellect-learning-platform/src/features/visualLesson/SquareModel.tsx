import { useState } from 'react';

export function SquareModel({ side, onSide, reveal = true, target }: { side: number; onSide?: (side: number) => void; reveal?: boolean; target?: number }) {
  const [rows, setRows] = useState(false);
  return <div className="garden-model">
    <div className="garden-model-top"><span>ВИД СВЕРХУ</span><button type="button" aria-pressed={rows} onClick={() => setRows(!rows)}>{rows ? 'Убрать выделение' : 'Выделить ряд'}</button></div>
    <svg viewBox="0 0 380 330" role="img" aria-label={`Квадрат со стороной ${side} метров, ${side * side} клеток по одному квадратному метру`}>
      <defs><pattern id="garden-dots" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#ccd6cc" /></pattern></defs>
      <rect width="380" height="330" fill="url(#garden-dots)" />
      {Array.from({ length: side * side }, (_, i) => {
        const unit = 27; const start = (380 - side * unit) / 2;
        return <rect key={i} x={start + (i % side) * unit} y={148 - side * unit / 2 + Math.floor(i / side) * unit} width={unit - 2} height={unit - 2} rx="4" fill={rows && i < side ? '#e6ac55' : '#7caa89'} stroke={rows && i < side ? '#aa7224' : '#527d60'} className="garden-tile" />;
      })}
      <path d={`M${(380 - side * 27) / 2} ${162 + side * 27 / 2} v8 h${side * 27 - 2} v-8`} fill="none" stroke="#426451" strokeWidth="1.5" />
      <text x="190" y={194 + side * 27 / 2} textAnchor="middle" fill="#244434" fontSize="17" fontWeight="600">{side} м</text>
    </svg>
    <div className="garden-model-legend"><i /> Одна клетка = 1 м² {rows && <span>· В ряду {side} клеток</span>}</div>
    {onSide && <div className="garden-slider"><label htmlFor="garden-side">Длина стороны <strong>{side} м</strong></label><input id="garden-side" type="range" min="1" max="8" step="1" value={side} onChange={event => onSide(Number(event.target.value))} /><div><span>1 м</span><span>8 м</span></div></div>}
    {reveal && <div className="garden-equation"><span>{side} × {side}</span><span>=</span><strong>{side * side} <small>м²</small></strong></div>}
    {target && <p className="garden-model-caption" role="status">{side * side === target ? `Получилось! ${side} ряда по ${side} клетки — ровно ${target} м².` : `Сейчас ${side * side} м². ${side * side < target ? 'Увеличь' : 'Уменьши'} сторону, чтобы получить ${target} м².`}</p>}
  </div>;
}
