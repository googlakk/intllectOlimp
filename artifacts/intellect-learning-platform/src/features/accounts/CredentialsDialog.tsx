import { useState } from 'react';
import { Copy, Download } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import type { IssuedCredentials } from '@/lib/api';
import { credentialsCsv } from './credentialBatch';

export function CredentialsDialog({ credentials, onClose }: { credentials: IssuedCredentials[]; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const text = credentials.map(item => [item.display_name, item.login, item.temporary_password].filter(Boolean).join('\t')).join('\n');
  const download = () => {
    const url = URL.createObjectURL(new Blob([credentialsCsv(credentials)], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'Данные_для_входа.csv'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <Dialog open onOpenChange={open => { if (!open) onClose(); }}><DialogContent className="max-w-2xl">
    <DialogTitle>Данные для входа · {credentials.length}</DialogTitle>
    <DialogDescription>Сохраните список: пароли показываются один раз. Передайте каждому ученику его данные.</DialogDescription>
    <div className="max-h-72 overflow-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-2">Ученик</th><th className="p-2">Логин</th><th className="p-2">Временный пароль</th></tr></thead><tbody>{credentials.map(item => <tr key={item.profile_id} className="border-t"><td className="p-2">{item.display_name || '—'}</td><td className="p-2 font-mono">{item.login}</td><td className="p-2 font-mono">{item.temporary_password}</td></tr>)}</tbody></table></div>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <div className="flex flex-wrap justify-end gap-2"><button onClick={async () => { try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setError('Не удалось скопировать. Скачайте CSV.'); } }} className="inline-flex h-10 items-center gap-2 rounded-md border px-3"><Copy className="h-4 w-4" />{copied ? 'Скопировано' : 'Копировать'}</button><button onClick={download} className="inline-flex h-10 items-center gap-2 rounded-md border px-3"><Download className="h-4 w-4" />Скачать CSV</button><button onClick={onClose} className="h-10 rounded-md bg-primary px-4 font-semibold text-primary-foreground">Готово</button></div>
  </DialogContent></Dialog>;
}
