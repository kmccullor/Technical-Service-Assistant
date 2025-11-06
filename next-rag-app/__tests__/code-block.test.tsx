import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CodeBlock } from '../components/ui/code-block';

// Mock clipboard API
Object.defineProperty(global.navigator, 'clipboard', {
  value: {
    writeText: jest.fn().mockResolvedValue(undefined),
  },
  writable: true,
});

describe('CodeBlock component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders code with copy button', () => {
    render(<CodeBlock code="console.log('hello');" language="javascript" />);

    expect(screen.getByText("console.log('hello');")).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /copy code/i })).toBeInTheDocument();
  });

  it('copies code to clipboard when copy button is clicked', async () => {
    render(<CodeBlock code="const x = 42;" />);

    const copyButton = screen.getByRole('button', { name: /copy code/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('const x = 42;');
    });
  });

  it('shows check icon when copy is successful', async () => {
    render(<CodeBlock code="test code" />);

    const copyButton = screen.getByRole('button', { name: /copy code/i });
    fireEvent.click(copyButton);

    // Check that the button now contains the Check icon
    await waitFor(() => {
      const checkIcon = copyButton.querySelector('.lucide-check');
      expect(checkIcon).toBeInTheDocument();
    });

    // Check icon should disappear after 2 seconds
    await waitFor(() => {
      const checkIcon = copyButton.querySelector('.lucide-check');
      expect(checkIcon).not.toBeInTheDocument();
    }, { timeout: 2500 });
  });

  it('handles copy failure gracefully', async () => {
    (global.navigator.clipboard.writeText as jest.Mock).mockRejectedValueOnce(new Error('Copy failed'));

    // Mock console.error to avoid test output pollution
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    render(<CodeBlock code="error code" />);

    const copyButton = screen.getByRole('button', { name: /copy code/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to copy code:', expect.any(Error));
    });

    consoleSpy.mockRestore();
  });
});