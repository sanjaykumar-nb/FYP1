import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      gcTime: 0,
    },
  },
})

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
)

describe('UI Components', () => {
  describe('Button', () => {
    it('renders correctly', () => {
      render(<Button>Click me</Button>, { wrapper })
      expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument()
    })

    it('handles click events', () => {
      const handleClick = vi.fn()
      render(<Button onClick={handleClick}>Click me</Button>, { wrapper })
      fireEvent.click(screen.getByRole('button'))
      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('applies variant classes', () => {
      render(<Button variant="outline">Outline</Button>, { wrapper })
      const button = screen.getByRole('button')
      expect(button).toHaveClass('border')
    })

    it('applies size classes', () => {
      render(<Button size="sm">Small</Button>, { wrapper })
      const button = screen.getByRole('button')
      expect(button).toHaveClass('h-9')
    })

    it('shows loading state', () => {
      render(<Button disabled>Loading</Button>, { wrapper })
      expect(screen.getByRole('button')).toBeDisabled()
    })
  })

  describe('Card', () => {
    it('renders card with header and content', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>Test Title</CardTitle>
          </CardHeader>
          <CardContent>Test content</CardContent>
        </Card>,
        { wrapper }
      )
      expect(screen.getByText('Test Title')).toBeInTheDocument()
      expect(screen.getByText('Test content')).toBeInTheDocument()
    })
  })

  describe('Badge', () => {
    it('renders with default variant', () => {
      render(<Badge>Default</Badge>, { wrapper })
      expect(screen.getByText('Default')).toBeInTheDocument()
    })

    it('applies variant classes', () => {
      render(<Badge variant="destructive">Destructive</Badge>, { wrapper })
      const badge = screen.getByText('Destructive')
      expect(badge).toHaveClass('bg-destructive')
    })

    it('applies outline variant', () => {
      render(<Badge variant="outline">Outline</Badge>, { wrapper })
      const badge = screen.getByText('Outline')
      expect(badge).toHaveClass('border')
    })
  })

  describe('Input', () => {
    it('renders input field', () => {
      render(<Input placeholder="Enter text" />, { wrapper })
      expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument()
    })

    it('handles value changes', () => {
      render(<Input defaultValue="initial" />, { wrapper })
      const input = screen.getByDisplayValue('initial')
      fireEvent.change(input, { target: { value: 'updated' } })
      expect(input).toHaveValue('updated')
    })

    it('applies disabled state', () => {
      render(<Input disabled />, { wrapper })
      expect(screen.getByRole('textbox')).toBeDisabled()
    })
  })

  describe('Progress', () => {
    it('renders progress bar with value', () => {
      render(<Progress value={50} />, { wrapper })
      const progress = screen.getByRole('progressbar')
      expect(progress).toHaveAttribute('aria-valuenow', '50')
    })

    it('applies custom className', () => {
      render(<Progress value={75} className="h-4" />, { wrapper })
      const progress = screen.getByRole('progressbar')
      expect(progress).toHaveClass('h-4')
    })
  })
})

describe('Utility Functions', () => {
  it('cn utility combines classes correctly', () => {
    expect(cn('base', 'conditional', false && 'hidden')).toBe('base conditional')
    expect(cn('base', { conditional: true, hidden: false })).toBe('base conditional')
  })
})