import { useSyncExternalStore, type ReactNode } from 'react';
import { isPhoneDevice } from './phoneDevice';
import { PhoneLanding } from './PhoneLanding';

function getPhoneSnapshot() {
  return isPhoneDevice({
    userAgent: navigator.userAgent,
    coarsePointer: window.matchMedia('(pointer: coarse)').matches,
    screenWidth: window.screen.width,
    screenHeight: window.screen.height,
  });
}

function subscribe(onChange: () => void) {
  const pointer = window.matchMedia('(pointer: coarse)');
  window.addEventListener('resize', onChange);
  pointer.addEventListener('change', onChange);
  return () => {
    window.removeEventListener('resize', onChange);
    pointer.removeEventListener('change', onChange);
  };
}

export function PhoneAccessGate({ children }: { children: ReactNode }) {
  const isPhone = useSyncExternalStore(subscribe, getPhoneSnapshot, () => false);
  return isPhone ? <PhoneLanding /> : children;
}
