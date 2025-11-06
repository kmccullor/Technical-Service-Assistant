import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MessageRenderer } from '../components/chat/message-renderer';

// Mock clipboard API
Object.defineProperty(global.navigator, 'clipboard', {
  value: {
    writeText: jest.fn().mockResolvedValue(undefined),
  },
  writable: true,
});

describe('Code Copying Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders and allows copying code from a realistic AI response', async () => {
    const aiResponse = `Here's a Python function to solve your problem:

\`\`\`python
def calculate_fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# Example usage
result = calculate_fibonacci(10)
print(f"The 10th Fibonacci number is: {result}")
\`\`\`

This recursive implementation is simple but not efficient for large n values. For production use, consider an iterative approach.`;

    render(<MessageRenderer content={aiResponse} />);

    // Check that the text content is rendered
    expect(screen.getByText("Here's a Python function to solve your problem:")).toBeInTheDocument();
    expect(screen.getByText("This recursive implementation is simple but not efficient for large n values. For production use, consider an iterative approach.")).toBeInTheDocument();

    // Check that the code block is rendered with syntax highlighting
    const codeElement = document.querySelector('code');
    expect(codeElement).toBeInTheDocument();
    expect(codeElement?.className).toContain('language-python');

    // Check that the full code is present
    expect(codeElement?.textContent).toContain('def calculate_fibonacci(n):');
    expect(codeElement?.textContent).toContain('print(f"The 10th Fibonacci number is: {result}")');

    // Check that copy button is present
    const copyButton = screen.getByRole('button', { name: /copy code/i });
    expect(copyButton).toBeInTheDocument();

    // Simulate clicking the copy button
    fireEvent.click(copyButton);

    // Verify that the clipboard API was called with the correct code
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(`def calculate_fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# Example usage
result = calculate_fibonacci(10)
print(f"The 10th Fibonacci number is: {result}")`);
    });
  });

  it('handles multiple code blocks in a single response', () => {
    const responseWithMultipleCodeBlocks = `Here are two approaches:

**Approach 1: List Comprehension**
\`\`\`python
squares = [x**2 for x in range(10)]
\`\`\`

**Approach 2: Map Function**
\`\`\`python
squares = list(map(lambda x: x**2, range(10)))
\`\`\`

Both produce the same result but have different performance characteristics.`;

    render(<MessageRenderer content={responseWithMultipleCodeBlocks} />);

    // Check text content using more flexible matching
    expect(screen.getByText(/Here are two approaches/)).toBeInTheDocument();
    expect(screen.getByText(/Both produce the same result/)).toBeInTheDocument();

    // Check that we have two code blocks with copy buttons
    const codeElements = document.querySelectorAll('code');
    expect(codeElements).toHaveLength(2);

    const copyButtons = screen.getAllByRole('button', { name: /copy code/i });
    expect(copyButtons).toHaveLength(2);

    // Verify the code content in each block
    expect(codeElements[0]?.textContent).toBe('squares = [x**2 for x in range(10)]');
    expect(codeElements[1]?.textContent).toBe('squares = list(map(lambda x: x**2, range(10)))');
  });

  it('gracefully handles responses without code blocks', () => {
    const plainResponse = "This is a regular text response without any code blocks. Just plain old text that should render normally.";

    render(<MessageRenderer content={plainResponse} />);

    // Check that the text is rendered
    expect(screen.getByText(plainResponse)).toBeInTheDocument();

    // No code elements or copy buttons should be present
    const codeElements = document.querySelectorAll('code');
    expect(codeElements).toHaveLength(0);

    const copyButtons = screen.queryAllByRole('button', { name: /copy code/i });
    expect(copyButtons).toHaveLength(0);
  });
});