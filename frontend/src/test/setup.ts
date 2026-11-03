import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => cleanup())

// jsdom has no layout engine; components that measure themselves get a fixed width.
class FixedResizeObserver implements ResizeObserver {
  private readonly callback: ResizeObserverCallback
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }
  observe(target: Element): void {
    this.callback([{ target, contentRect: { width: 360, height: 132 } } as ResizeObserverEntry], this)
  }
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver = FixedResizeObserver

// jsdom has no matchMedia either; the theme provider asks for prefers-color-scheme.
window.matchMedia ??= (query: string) =>
  ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }) as MediaQueryList
