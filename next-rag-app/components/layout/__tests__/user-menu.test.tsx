import { render, screen, fireEvent } from '@testing-library/react'
import { UserMenu } from '../user-menu'
import { useAuth } from '@/src/context/AuthContext'

// Mock the auth context
jest.mock('@/src/context/AuthContext', () => ({
  useAuth: jest.fn(),
}))

// Mock Next.js Link component
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  )
  MockLink.displayName = 'NextLinkMock'
  return MockLink
})

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>

describe('UserMenu', () => {
  const mockUser = {
    id: 1,
    email: 'test@example.com',
    full_name: 'Test User',
    role_name: 'user',
    role_id: 2,
    password_change_required: false,
    status: 'active',
    verified: true,
  }

  const mockAuthContext = {
    user: null as any,
    login: jest.fn(),
    logout: jest.fn(),
    register: jest.fn(),
    refresh: jest.fn(),
    accessToken: null,
    refreshToken: null,
    expiresAt: null,
    loading: false,
    error: null,
    clearError: jest.fn(),
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders nothing when user is not logged in', () => {
    mockUseAuth.mockReturnValue({
      ...mockAuthContext,
      user: null,
    })

    const { container } = render(<UserMenu />)
    expect(container.firstChild).toBeNull()
  })

  it('renders user menu when user is logged in', () => {
    mockUseAuth.mockReturnValue({
      ...mockAuthContext,
      user: mockUser,
    })

    render(<UserMenu />)
    
    // Check if user name is displayed
    expect(screen.getByText('Test User')).toBeInTheDocument()
    expect(screen.getByText('user')).toBeInTheDocument()
  })

  it('shows dropdown menu when clicked', async () => {
    mockUseAuth.mockReturnValue({
      ...mockAuthContext,
      user: mockUser,
    })

    render(<UserMenu />)
    
    // Click on the user menu trigger
    const trigger = screen.getByText('Test User').closest('button')
    expect(trigger).toBeInTheDocument()
    
    if (trigger) {
      fireEvent.click(trigger)
    }
    
    // Check if dropdown items are visible
    expect(screen.getByText('Change Password')).toBeInTheDocument()
    expect(screen.getByText('Logout')).toBeInTheDocument()
    expect(screen.getByText('test@example.com')).toBeInTheDocument()
  })

  it('calls logout function when logout is clicked', async () => {
    const mockLogout = jest.fn()
    mockUseAuth.mockReturnValue({
      ...mockAuthContext,
      user: mockUser,
      logout: mockLogout,
    })

    render(<UserMenu />)
    
    // Click on the user menu trigger
    const trigger = screen.getByText('Test User').closest('button')
    if (trigger) {
      fireEvent.click(trigger)
    }
    
    // Click on logout
    const logoutButton = screen.getByText('Logout')
    fireEvent.click(logoutButton)
    
    expect(mockLogout).toHaveBeenCalledTimes(1)
  })

  it('displays role name correctly for admin users', () => {
    const adminUser = {
      ...mockUser,
      role_name: 'admin',
    }

    mockUseAuth.mockReturnValue({
      ...mockAuthContext,
      user: adminUser,
    })

    render(<UserMenu />)
    
    expect(screen.getByText('admin')).toBeInTheDocument()
  })

  it('displays role ID when role name is not available', () => {
    const userWithoutRoleName = {
      ...mockUser,
      role_name: null,
      role_id: 3,
    }

    mockUseAuth.mockReturnValue({
      ...mockAuthContext,
      user: userWithoutRoleName,
    })

    render(<UserMenu />)
    
    expect(screen.getByText('role 3')).toBeInTheDocument()
  })
})
