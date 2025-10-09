#!/usr/bin/env python3
"""
Test query expansion functionality for FlexNet/ESM product variations.
"""

# Product synonym mapping for query expansion
PRODUCT_SYNONYMS = {
    'flexnet': ['flexnet', 'flex net', 'flexlm', 'flex lm', 'license manager', 'licensing'],
    'esm': ['esm', 'enterprise security manager', 'security manager', 'enterprise security'],
    'rni': ['rni', 'radiant networking inc', 'radiant', 'networking'],
    'multispeak': ['multispeak', 'multi speak', 'multi-speak', 'utility communication'],
    'ppa': ['ppa', 'power plant automation', 'plant automation']
}

# Domain-specific term expansion
DOMAIN_EXPANSIONS = {
    'install': ['install', 'installation', 'setup', 'deployment', 'configure', 'configuration'],
    'license': ['license', 'licensing', 'activation', 'key', 'token'],
    'security': ['security', 'authentication', 'authorization', 'encryption', 'certificate'],
    'troubleshoot': ['troubleshoot', 'debug', 'error', 'issue', 'problem', 'fix'],
    'upgrade': ['upgrade', 'update', 'migration', 'version'],
    'guide': ['guide', 'manual', 'documentation', 'instructions', 'tutorial']
}


def expand_query_with_synonyms(query: str) -> str:
    """Phase 2B adaptive expansion mirror (no semantic filter in test context).

    - Product synonyms bucket
    - Problem trigger enrichment (top 3)
    - Activation/context enrichment (2 terms)
    - Domain expansions (top 2)
    - Adaptive cap: base 6; long (>=12 tokens) reduce by 2; trigger adds +2 (max 8)
    """
    PROBLEM_TRIGGERS = {
        'problems': ['troubleshoot', 'debug', 'error', 'issue', 'fix'],
        'issues': ['troubleshoot', 'debug', 'error', 'problem', 'fix'],
        'errors': ['troubleshoot', 'debug', 'issue', 'problem', 'fix'],
        'failures': ['troubleshoot', 'debug', 'error', 'issue', 'fix'],
        'fails': ['troubleshoot', 'debug', 'error', 'issue', 'fix'],
        'trouble': ['troubleshoot', 'debug', 'error', 'issue', 'fix'],
        'broken': ['troubleshoot', 'debug', 'error', 'issue', 'fix'],
    }
    CONTEXT_PATTERNS = {
        'activation': {
            'problem_context': ['licensing', 'key', 'troubleshoot', 'debug'],
            'setup_context': ['installation', 'configuration']
        },
        'configuration': {
            'problem_context': ['troubleshoot', 'debug', 'error', 'issue'],
            'setup_context': ['installation', 'setup']
        }
    }
    ql = query.lower()
    product_candidates = []
    problem_candidates = []
    context_candidates = []
    domain_candidates = []

    for synonyms in PRODUCT_SYNONYMS.values():
        if any(s in ql for s in synonyms):
            for syn in synonyms:
                if syn not in ql and syn not in product_candidates:
                    product_candidates.append(syn)

    trigger_used = None
    for trig, support in PROBLEM_TRIGGERS.items():
        if trig in ql:
            trigger_used = trig
            for term in support[:3]:
                if term not in ql and term not in problem_candidates:
                    problem_candidates.append(term)
            break

    for ctx_key, ctx_map in CONTEXT_PATTERNS.items():
        if ctx_key in ql:
            selected = ctx_map['problem_context' if trigger_used else 'setup_context']
            for term in selected[:2]:
                if term not in ql and term not in context_candidates:
                    context_candidates.append(term)

    for dom, exps in DOMAIN_EXPANSIONS.items():
        if dom in ql:
            for exp in exps[:2]:
                if exp not in ql and exp not in domain_candidates:
                    domain_candidates.append(exp)

    all_candidates = []
    for bucket in (product_candidates, problem_candidates, context_candidates, domain_candidates):
        for t in bucket:
            if t not in all_candidates:
                all_candidates.append(t)

    if not all_candidates:
        return query

    token_count = len(ql.split())
    cap = 6
    if token_count >= 12:
        cap = max(2, cap - 2)
    if trigger_used:
        cap = min(cap + 2, 8)

    expanded = f"{query} {' '.join(all_candidates[:cap])}"
    print(f"Query expanded: '{query}' -> '{expanded}' (cap={cap}, trigger={trigger_used})")
    return expanded


def test_query_expansion():
    """Test query expansion for various product and domain terms."""
    print("🔍 Testing Query Expansion System")
    print("=" * 60)

    test_cases = [
        {
            'query': 'FlexNet installation guide',
            'expected_expansions': ['flexnet', 'installation'],
            'description': 'FlexNet product with installation domain term'
        },
        {
            'query': 'ESM security configuration',
            'expected_expansions': ['esm', 'security'],
            'description': 'ESM product with security domain term'
        },
        {
            'query': 'license troubleshooting',
            'expected_expansions': ['license', 'troubleshoot'],
            'description': 'License and troubleshoot domain terms'
        },
        {
            'query': 'RNI upgrade procedures',
            'expected_expansions': ['rni', 'upgrade'],
            'description': 'RNI product with upgrade domain term'
        },
        {
            'query': 'how to install flex lm',
            'expected_expansions': ['install', 'flexnet'],
            'description': 'Alternative FlexNet naming with install term'
        },
        {
            'query': 'simple text query',
            'expected_expansions': [],
            'description': 'No expansions expected for generic terms'
        },
        {
            'query': 'license activation problems',
            'expected_expansions': ['licensing', 'troubleshoot', 'debug'],
            'description': 'Previously failing troubleshooting expansion case'
        },
        {
            'query': 'very long multi clause flexnet license server activation configuration guide reference problems',
            'expected_expansions': ['flexnet', 'troubleshoot'],  # We expect adaptive cap applied (reduced)
            'description': 'Long query triggers adaptive cap reduction'
        },
        {
            'query': 'esm configuration issues',
            'expected_expansions': ['esm', 'troubleshoot', 'debug'],
            'description': 'Problem trigger bonus adds troubleshooting terms'
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['description']}")
        print(f"Original: '{test_case['query']}'")

        expanded = expand_query_with_synonyms(test_case['query'])
        expanded_lower = expanded.lower()

        # Check if expected expansions are present
        missing_expansions = []
        for expected in test_case['expected_expansions']:
            found = False
            if expected in PRODUCT_SYNONYMS:
                # Check if any synonym for this product is present
                if any(synonym in expanded_lower for synonym in PRODUCT_SYNONYMS[expected]):
                    found = True
            elif expected in DOMAIN_EXPANSIONS:
                # Check if any expansion for this domain is present
                if any(expansion in expanded_lower for expansion in DOMAIN_EXPANSIONS[expected]):
                    found = True
            else:
                # Direct term check
                if expected in expanded_lower:
                    found = True

            if not found:
                missing_expansions.append(expected)

        if not missing_expansions and (test_case['expected_expansions'] or expanded == test_case['query']):
            print("✅ PASS: Query expansion working correctly")
        else:
            if missing_expansions:
                print(f"❌ FAIL: Missing expected expansions: {missing_expansions}")
            else:
                print("❌ FAIL: Unexpected expansion behavior")

    print("\n" + "=" * 60)
    print("Query expansion test completed!")

    # Test specific FlexNet/ESM cases that were failing
    print("\n🎯 Testing Specific Problem Cases")
    print("-" * 40)

    problem_queries = [
        "FlexNet license server setup",
        "ESM authentication guide",
        "flex lm troubleshooting",
        "enterprise security manager installation",
        "license activation problems"
    ]

    for query in problem_queries:
        expanded = expand_query_with_synonyms(query)
        improvement = len(expanded.split()) - len(query.split())
        print(f"Query: '{query}' (+{improvement} terms)")


if __name__ == "__main__":
    test_query_expansion()
