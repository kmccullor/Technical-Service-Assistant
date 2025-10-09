"use client"

import * as React from "react"
import { X } from "lucide-react"
import { Button } from "./button"

interface DialogProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: React.ReactNode
}

interface DialogContentProps {
  className?: string
  children: React.ReactNode
}

interface DialogTriggerProps {
  asChild?: boolean
  children: React.ReactNode
}

interface DialogHeaderProps {
  children: React.ReactNode
}

interface DialogTitleProps {
  children: React.ReactNode
}

interface DialogDescriptionProps {
  children: React.ReactNode
}

const Dialog = ({ open, onOpenChange, children }: DialogProps) => {
  const [isOpen, setIsOpen] = React.useState(open || false)

  React.useEffect(() => {
    if (open !== undefined) {
      setIsOpen(open)
    }
  }, [open])

  const handleOpenChange = (newOpen: boolean) => {
    setIsOpen(newOpen)
    onOpenChange?.(newOpen)
  }

  return (
    <DialogProvider value={{ open: isOpen, onOpenChange: handleOpenChange }}>
      {children}
    </DialogProvider>
  )
}

const DialogContext = React.createContext<{
  open: boolean
  onOpenChange: (open: boolean) => void
} | null>(null)

const DialogProvider = DialogContext.Provider

const useDialog = () => {
  const context = React.useContext(DialogContext)
  if (!context) {
    throw new Error("useDialog must be used within Dialog")
  }
  return context
}

const DialogTrigger = ({ asChild, children }: DialogTriggerProps) => {
  const { open, onOpenChange } = useDialog()

  const handleClick = () => {
    onOpenChange(!open)
  }

  if (asChild) {
    return React.cloneElement(children as React.ReactElement, {
      onClick: handleClick
    })
  }

  return (
    <Button onClick={handleClick}>
      {children}
    </Button>
  )
}

const DialogContent = ({ className = "", children }: DialogContentProps) => {
  const { open, onOpenChange } = useDialog()

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50" 
        onClick={() => onOpenChange(false)}
      />
      
      {/* Content */}
      <div className={`relative bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 w-full max-w-md mx-4 ${className}`}>
        <Button
          variant="ghost"
          size="sm"
          className="absolute right-2 top-2 p-1 h-6 w-6"
          onClick={() => onOpenChange(false)}
        >
          <X className="h-4 w-4" />
        </Button>
        {children}
      </div>
    </div>
  )
}

const DialogHeader = ({ children }: DialogHeaderProps) => (
  <div className="mb-4">
    {children}
  </div>
)

const DialogTitle = ({ children }: DialogTitleProps) => (
  <h2 className="text-lg font-semibold">
    {children}
  </h2>
)

const DialogDescription = ({ children }: DialogDescriptionProps) => (
  <p className="text-sm text-muted-foreground">
    {children}
  </p>
)

export {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
}