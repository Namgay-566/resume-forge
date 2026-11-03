import { useReducedMotion } from 'framer-motion'
import { useEffect, useState } from 'react'

/** Cycle through `count` items every `ms`. Stops while `hold` is true (hover or focus),
 * when the user pauses it, and entirely for people who prefer reduced motion (WCAG 2.2.2). */
export function useRotation(count: number, ms: number) {
  const reduce = useReducedMotion()
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const [hold, setHold] = useState(false)
  const running = !reduce && !paused && !hold && count > 1
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % count), ms)
    return () => window.clearInterval(timer)
  }, [running, count, ms])
  return {
    index,
    /** Picking one by hand stops the rotation. */
    select: (i: number) => {
      setIndex(i)
      setPaused(true)
    },
    paused: paused || Boolean(reduce),
    canRotate: !reduce && count > 1,
    togglePause: () => setPaused((p) => !p),
    holdProps: {
      onMouseEnter: () => setHold(true),
      onMouseLeave: () => setHold(false),
      onFocus: () => setHold(true),
      onBlur: () => setHold(false),
    },
  }
}
