import { describe, expect, it } from 'vitest';
import { isPhoneDevice } from './phoneDevice';

const desktop = { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', coarsePointer: false, screenWidth: 1440, screenHeight: 900 };

describe('temporary phone access notice', () => {
  it.each([
    { ...desktop, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)', screenWidth: 390, screenHeight: 844 },
    { ...desktop, userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/130.0 Mobile Safari/537.36', screenWidth: 844, screenHeight: 390 },
    { ...desktop, coarsePointer: true, screenWidth: 844, screenHeight: 390 },
    { ...desktop, userAgent: 'Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Safari/537.36', coarsePointer: true, screenWidth: 390, screenHeight: 844 },
  ])('keeps phone access blocked, including landscape and desktop-site mode: %j', signals => {
    expect(isPhoneDevice(signals)).toBe(true);
  });

  it.each([
    desktop,
    { ...desktop, screenWidth: 390, screenHeight: 844 },
    { ...desktop, coarsePointer: true },
    { ...desktop, coarsePointer: true, screenWidth: 744, screenHeight: 1133 },
    { ...desktop, userAgent: 'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X)', coarsePointer: true, screenWidth: 768, screenHeight: 1024 },
    { ...desktop, userAgent: 'Mozilla/5.0 (Linux; Android 14; Tablet) Chrome/130.0 Safari/537.36', coarsePointer: true, screenWidth: 600, screenHeight: 960 },
    { ...desktop, coarsePointer: true, screenWidth: 0, screenHeight: 0 },
  ])('preserves access from desktops, small desktop windows and tablets: %j', signals => {
    expect(isPhoneDevice(signals)).toBe(false);
  });
});
