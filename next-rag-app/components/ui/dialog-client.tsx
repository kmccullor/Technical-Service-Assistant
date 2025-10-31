'use client'

import dynamic from 'next/dynamic'

// Individual dynamic imports for each dialog component to prevent SSR hydration issues
export const Dialog = dynamic(() => import('@/components/ui/dialog').then(mod => ({ default: mod.Dialog })), {
  ssr: false,
  loading: () => null
})

export const DialogContent = dynamic(() => import('@/components/ui/dialog').then(mod => ({ default: mod.DialogContent })), {
  ssr: false,
  loading: () => null
})

export const DialogHeader = dynamic(() => import('@/components/ui/dialog').then(mod => ({ default: mod.DialogHeader })), {
  ssr: false,
  loading: () => null
})

export const DialogTitle = dynamic(() => import('@/components/ui/dialog').then(mod => ({ default: mod.DialogTitle })), {
  ssr: false,
  loading: () => null
})

export const DialogTrigger = dynamic(() => import('@/components/ui/dialog').then(mod => ({ default: mod.DialogTrigger })), {
  ssr: false,
  loading: () => null
})

export const DialogDescription = dynamic(() => import('@/components/ui/dialog').then(mod => ({ default: mod.DialogDescription })), {
  ssr: false,
  loading: () => null
})
