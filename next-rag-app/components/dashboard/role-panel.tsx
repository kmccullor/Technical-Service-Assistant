'use client'

import React from 'react'
import { Button } from '@/components/ui/button'
import { UserMenu } from '@/components/layout/user-menu'
import type { UserInfo } from '@/src/context/AuthContext'

const ROLE_OPTIONS = [
  { id: 'admin', label: 'Admin', description: 'Full visibility, dashboards, and configuration controls.' },
  { id: 'employee', label: 'Employee', description: 'Case ownership, research, and recommendation workflows.' },
  { id: 'guest', label: 'Guest', description: 'Read-only context and observation-only navigation.' },
]

interface RolePanelProps {
  user: UserInfo
  selectedRoleView: string
  onRoleChange: (role: string) => void
}

export function RolePanel({ user, selectedRoleView, onRoleChange }: RolePanelProps) {
  const normalizedRole = (user.role_name || 'guest').toLowerCase()

  return (
    <div className="space-y-4 px-4 py-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Role aware sidebar</p>
          <p className="text-lg font-semibold">{user.full_name}</p>
          <p className="text-xs text-muted-foreground">{user.email}</p>
          <p className="text-xs text-primary-foreground">Current role: {user.role_name || 'Guest'}</p>
          <p className="text-xs text-muted-foreground">Status: {user.status}</p>
        </div>
        <div>
          <UserMenu />
        </div>
      </div>
      <div className="space-y-2">
        {ROLE_OPTIONS.map((option) => (
          <div key={option.id} className="flex flex-col gap-1">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-sm font-medium">{option.label}</p>
                <p className="text-xs text-muted-foreground truncate">{option.description}</p>
              </div>
              <Button
                size="sm"
                variant={selectedRoleView === option.id ? 'secondary' : 'outline'}
                className="text-xs"
                onClick={() => onRoleChange(option.id)}
                disabled={normalizedRole === option.id && option.id !== 'guest'}
              >
                Continue as {option.label}
              </Button>
            </div>
            <div className="h-px bg-border/60" />
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Research is powered by the shared Postgres + pgvector knowledge base for the Sensus AMI catalog.
        Role-aware filtering keeps Salesforce case answers aligned with what each persona should view.
      </p>
    </div>
  )
}
