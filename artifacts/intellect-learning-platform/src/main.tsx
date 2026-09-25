import { createRoot } from 'react-dom/client';

import App from './App';
import { ErrorBoundary } from '@/components/error-boundary';

import './index.css';
import 'katex/dist/katex.min.css';

if (import.meta.env.DEV) {
  // «ResizeObserver loop…» безвреден: браузер доставит размеры в следующем кадре.
  // Он приходит без объекта ошибки, и оверлей Vite показывает его как
  // «unknown runtime error» (например, на доске связей React Flow). Остальные
  // ошибки оверлей видит как раньше. Слушатель на фазе перехвата срабатывает
  // раньше слушателя оверлея.
  window.addEventListener('error', (event) => {
    if (event.message?.startsWith('ResizeObserver loop')) event.stopImmediatePropagation();
  }, true);
}

createRoot(document.getElementById('root')!, {
  // Keeps caught errors off reportError(), which would raise the dev overlay.
  onCaughtError: (error, errorInfo) => {
    console.error(error, errorInfo.componentStack);
  },
}).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
