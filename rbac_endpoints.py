#!/usr/bin/env python3
"""
Compatibility Shim for rbac_endpoints

Re-exports from reranker.rbac_endpoints to maintain backward compatibility
while eliminating code duplication and type errors.
"""

# Import all symbols from the active implementation
from reranker.rbac_endpoints import (
    rbac_router,
    router,  # alias
)

# Re-export for backward compatibility
__all__ = [
    'rbac_router',
    'router',
]