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

describe('MessageRenderer component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders plain text without code blocks', () => {
    render(<MessageRenderer content="This is a simple message without code." />);

    expect(screen.getByText('This is a simple message without code.')).toBeInTheDocument();
  });

  it('renders code block with language', () => {
    const content = 'Here is some code:\n\n```javascript\nfunction hello() {\n  console.log("Hello, World!");\n}\n```\n\nEnd of message.';
    const { container } = render(<MessageRenderer content={content} />);

    expect(screen.getByText('Here is some code:')).toBeInTheDocument();
    // Check that the code element contains the expected code
    const codeElement = container.querySelector('code');
    expect(codeElement).toBeInTheDocument();
    expect(codeElement?.textContent).toBe('function hello() {\n  console.log("Hello, World!");\n}');
    expect(screen.getByText('End of message.')).toBeInTheDocument();

    // Check that copy button is present
    expect(screen.getByRole('button', { name: /copy code/i })).toBeInTheDocument();
  });

  it('renders code block without language', () => {
    const content = '```\nconst x = 42;\n```';
    render(<MessageRenderer content={content} />);

    expect(screen.getByText('const x = 42;')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /copy code/i })).toBeInTheDocument();
  });

  it('renders multiple code blocks', () => {
    const content = 'First code:\n\n```python\nprint("Hello")\n```\n\nSecond code:\n\n```sql\nSELECT * FROM users;\n```\n\nEnd.';
    render(<MessageRenderer content={content} />);

    expect(screen.getByText('First code:')).toBeInTheDocument();
    expect(screen.getByText('print("Hello")')).toBeInTheDocument();
    expect(screen.getByText('Second code:')).toBeInTheDocument();
    expect(screen.getByText('SELECT * FROM users;')).toBeInTheDocument();
    expect(screen.getByText('End.')).toBeInTheDocument();

    // Should have two copy buttons
    const copyButtons = screen.getAllByRole('button', { name: /copy code/i });
    expect(copyButtons).toHaveLength(2);
  });

  it('handles code blocks at start and end', () => {
    const content = '```bash\necho "start"\n```\n\nMiddle text\n\n```\necho "end"\n```';
    render(<MessageRenderer content={content} />);

    expect(screen.getByText('echo "start"')).toBeInTheDocument();
    expect(screen.getByText('Middle text')).toBeInTheDocument();
    expect(screen.getByText('echo "end"')).toBeInTheDocument();
  });

  it('copies code when copy button is clicked', async () => {
    const content = '```javascript\nconsole.log("test");\n```';
    render(<MessageRenderer content={content} />);

    const copyButton = screen.getByRole('button', { name: /copy code/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('console.log("test");');
    });
  });

  it('handles malformed code blocks gracefully', () => {
    const content = '```javascript\nincomplete code block';
    const { container } = render(<MessageRenderer content={content} />);

    // Should render as plain text since the code block is malformed
    const spanElement = container.querySelector('span');
    expect(spanElement).toBeInTheDocument();
    expect(spanElement?.textContent).toBe('```javascript\nincomplete code block');
  });
});