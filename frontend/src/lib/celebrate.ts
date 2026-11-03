import confetti from 'canvas-confetti'

let fire: confetti.CreateTypes | null = null

/** A short, tasteful burst of confetti (brand colors). Skipped with "reduce motion".
 * Uses its own canvas on the main thread: canvas-confetti's default instance renders in a
 * blob-URL Web Worker, which the production CSP (no blob: workers) would block. */
export function celebrate(): void {
  if (typeof window === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  if (!fire) {
    const canvas = document.createElement('canvas')
    canvas.setAttribute('aria-hidden', 'true')
    Object.assign(canvas.style, { position: 'fixed', inset: '0', width: '100%', height: '100%', pointerEvents: 'none', zIndex: '60' })
    document.body.appendChild(canvas)
    fire = confetti.create(canvas, { resize: true, useWorker: false, disableForReducedMotion: true })
  }
  const colors = ['#4d49d7', '#7e89f5', '#f47431', '#fa8746', '#1f9d6e']
  const burst = (x: number, angle: number) =>
    fire?.({ particleCount: 70, spread: 62, startVelocity: 48, angle, origin: { x, y: 0.7 }, colors, scalar: 0.9, ticks: 180 })
  void burst(0.2, 60)
  void burst(0.8, 120)
}
