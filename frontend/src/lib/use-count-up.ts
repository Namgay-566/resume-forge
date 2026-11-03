import { animate, useInView, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

const EASE = [0.22, 1, 0.36, 1] as const

/** Counts from 0 to `value` the first time the element scrolls into view.
 * With "reduce motion" on, it shows the final value straight away. */
export function useCountUp<T extends Element = HTMLDivElement>(value: number, duration = 1.4) {
  const ref = useRef<T>(null)
  const inView = useInView(ref, { once: true, amount: 0.4 })
  const reduce = useReducedMotion()
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    if (!inView || reduce) return
    const controls = animate(0, value, { duration, ease: EASE, onUpdate: (v) => setCurrent(Math.round(v)) })
    return () => controls.stop()
  }, [inView, reduce, value, duration])

  return { ref, current: reduce ? value : current }
}
