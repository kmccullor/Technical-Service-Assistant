'use client'

import React from 'react'
import Link from 'next/link'
import { useAuth } from '@/src/context/AuthContext'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ChevronDown, User, Key, LogOut, Shield, BarChart3, Activity } from 'lucide-react'

interface UserMenuProps {
  className?: string
}

export function UserMenu({ className }: UserMenuProps) {
  const { user, logout } = useAuth()

  if (!user) {
    return null
  }
  const normalizedRoleName = typeof user.role_name === 'string' ? user.role_name.toLowerCase() : null
  const roleId = typeof user.role_id === 'string' ? Number.parseInt(user.role_id, 10) : user.role_id
  const isAdmin = normalizedRoleName === 'admin' || roleId === 1

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className={`flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer ${className}`}>
        <User className="h-4 w-4" />
        <span>{user.full_name}</span>
        <span className="ml-2 px-2 py-0.5 rounded bg-secondary text-xs uppercase">
          {user.role_name || 'role ' + user.role_id}
        </span>
        <ChevronDown className="h-4 w-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none">{user.full_name}</p>
            <p className="text-xs leading-none text-muted-foreground">
              {user.email}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {isAdmin && (
          <>
            <DropdownMenuItem asChild>
              <Link href="/admin" className="flex items-center cursor-pointer">
                <Shield className="mr-2 h-4 w-4" />
                <span>User / Role Management</span>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <a href="http://RNI-LLM-01.lab.sensus.net:3001" target="_blank" rel="noopener noreferrer" className="flex items-center cursor-pointer">
                <BarChart3 className="mr-2 h-4 w-4" />
                <span>Grafana Dashboard</span>
              </a>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <a href="http://RNI-LLM-01.lab.sensus.net:9091" target="_blank" rel="noopener noreferrer" className="flex items-center cursor-pointer">
                <Activity className="mr-2 h-4 w-4" />
                <span>Prometheus Server</span>
              </a>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem asChild>
          <Link href="/change-password" className="flex items-center cursor-pointer">
            <Key className="mr-2 h-4 w-4" />
            <span>Change Password</span>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={logout} className="flex items-center cursor-pointer text-red-600">
          <LogOut className="mr-2 h-4 w-4" />
          <span>Logout</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
