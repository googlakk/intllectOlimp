import { describe, expect, it } from 'vitest';
import { blockImage, inlineBlockMedia, SELF_MEDIA_COMPONENTS, INLINE_MEDIA_COMPONENTS } from './BlockMedia';

describe('block media', () => {
  it('accepts only images with a url', () => {
    expect(blockImage({ kind: 'image', url: '/a.png' })?.url).toBe('/a.png');
    expect(blockImage({ kind: 'video', url: '/a.mp4' })).toBeNull();
    expect(blockImage({ kind: 'image', url: '' })).toBeNull();
    expect(blockImage('x')).toBeNull();
  });

  it('reads media only from inline media blocks', () => {
    expect(inlineBlockMedia({ component: 'KeyConcept', content: { media: { url: '/a.png' } } })?.url).toBe('/a.png');
    expect(inlineBlockMedia({ component: 'MasteryCheck', content: { media: { url: '/a.png' } } })).toBeNull();
  });

  it('lets only inline media blocks place the image themselves', () => {
    for (const name of SELF_MEDIA_COMPONENTS) expect(INLINE_MEDIA_COMPONENTS.has(name)).toBe(true);
  });
});
