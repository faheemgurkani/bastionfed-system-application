'use client'

import { useRef, type ReactNode, type MouseEvent } from 'react'
import { cn } from '@/lib/utils'

interface CometCardProps {
  children: ReactNode
  /** Controls depth of 3D rotation on mouse movement. Higher = more dramatic. */
  rotateDepth?: number
  /** Controls the translateZ lift on hover. Higher = more dramatic pop. */
  translateDepth?: number
  className?: string
}

/**
 * Wraps any content in a perspective 3D tilt card — the same effect used on
 * Perplexity Comet's website. The wrapper div handles all 3D transforms;
 * the child element's own styling (borders, backgrounds, transitions) is
 * completely unaffected.
 */
export function CometCard({
  children,
  rotateDepth = 17.5,
  translateDepth = 20,
  className,
}: CometCardProps) {
  const ref = useRef<HTMLDivElement>(null)

  const onMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width - 0.5   // -0.5 → 0.5
    const y = (e.clientY - rect.top) / rect.height - 0.5   // -0.5 → 0.5
    el.style.transition = 'transform 0.08s linear'
    el.style.transform = `perspective(900px) rotateX(${-y * rotateDepth}deg) rotateY(${x * rotateDepth}deg) translateZ(${translateDepth}px)`
  }

  const onMouseLeave = () => {
    const el = ref.current
    if (!el) return
    el.style.transition = 'transform 0.5s ease'
    el.style.transform = 'perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0px)'
  }

  return (
    <div
      ref={ref}
      className={cn('w-full', className)}
      style={{ transformStyle: 'preserve-3d' }}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </div>
  )
}
