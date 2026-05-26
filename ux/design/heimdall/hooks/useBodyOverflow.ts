import { useEffect } from 'react'

let overflowRefCount = 0
let originalOverflow: string | null = null

export function useBodyOverflow(isActive: boolean) {
  useEffect(() => {
    if (!isActive) return

    if (overflowRefCount === 0) {
      originalOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
    }
    overflowRefCount++

    return () => {
      overflowRefCount--
      if (overflowRefCount === 0 && originalOverflow !== null) {
        document.body.style.overflow = originalOverflow
        originalOverflow = null
      }
    }
  }, [isActive])
}
