#!/usr/bin/env python3
"""
PyTorch warning suppression for CPU-only environments.
Configures torch DataLoader to disable pin_memory warnings.
"""

import os
import warnings


# Suppress specific PyTorch warnings for CPU-only usage
def configure_pytorch_cpu():
    """Configure PyTorch for CPU-only usage without warnings."""

    # Comprehensive warning suppression for pin_memory
    warnings.filterwarnings("ignore", message=".*pin_memory.*", category=UserWarning)
    warnings.filterwarnings("ignore", message=".*no accelerator.*", category=UserWarning)
    warnings.filterwarnings("ignore", module="torch.*", category=UserWarning)

    # Set environment variables for optimal CPU performance
    os.environ["PYTORCH_DISABLE_CUDNN_CACHE"] = "1"
    os.environ["OMP_NUM_THREADS"] = "4"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


# Auto-configure when imported
configure_pytorch_cpu()

# Alternative approach: monkey patch the warning

original_warn = warnings.warn


def filtered_warn(message, category=None, stacklevel=1, source=None):
    """Custom warning function that filters pin_memory warnings."""
    if isinstance(message, str) and "pin_memory" in message and "no accelerator" in message:
        return  # Skip pin_memory warnings
    # Call original with proper signature
    if category is None:
        category = UserWarning
    original_warn(message, category, stacklevel=stacklevel, source=source)


warnings.warn = filtered_warn
