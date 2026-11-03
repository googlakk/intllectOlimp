interface DeviceSignals {
  userAgent: string;
  coarsePointer: boolean;
  screenWidth: number;
  screenHeight: number;
}

/** Use device signals so rotating a phone or narrowing a desktop window keeps the same experience. */
export function isPhoneDevice(signals: DeviceSignals): boolean {
  const { userAgent, coarsePointer, screenWidth, screenHeight } = signals;
  if (/iPad|Tablet|PlayBook/i.test(userAgent)) return false;
  if (/iPhone|iPod|Android.*Mobile|Windows Phone|IEMobile|BlackBerry|BB10|Opera Mini/i.test(userAgent)) return true;

  // Desktop-site mode can hide the phone UA. Physical screen size still distinguishes it
  // from tablets (normally at least 600 CSS pixels on the shorter side).
  const shorterSide = Math.min(screenWidth, screenHeight);
  return coarsePointer && shorterSide > 0 && shorterSide < 600;
}
