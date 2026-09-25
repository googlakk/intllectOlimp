import { createContext, useContext } from 'react';
import type { TutorBridge } from './tutorBridge';

// Без провайдера (тьютор выключен, редактор, предпросмотр) блоки работают как раньше.
const TutorBridgeContext = createContext<TutorBridge>({});

export const TutorBridgeProvider = TutorBridgeContext.Provider;

export function useTutorBridge(): TutorBridge {
  return useContext(TutorBridgeContext);
}
