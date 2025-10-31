#!/usr/bin/env python3
"""
Phase 2 Accuracy Improvements - Quick Wins Implementation
Demonstrates enhanced query expansion and extended security patterns.
"""

import re

# Enhanced query expansion with problem detection
ENHANCED_PRODUCT_SYNONYMS = {
    "flexnet": ["flexnet", "flex net", "flexlm", "flex lm", "license manager", "licensing"],
    "esm": ["esm", "enterprise security manager", "security manager", "enterprise security"],
    "rni": ["rni", "radiant networking inc", "radiant", "networking"],
    "multispeak": ["multispeak", "multi speak", "multi-speak", "utility communication"],
    "ppa": ["ppa", "power plant automation", "plant automation"],
}

ENHANCED_DOMAIN_EXPANSIONS = {
    "install": ["install", "installation", "setup", "deployment", "configure", "configuration"],
    "license": ["license", "licensing", "activation", "key", "token"],
    "security": ["security", "authentication", "authorization", "encryption", "certificate"],
    "troubleshoot": ["troubleshoot", "debug", "error", "issue", "problem", "fix"],
    "upgrade": ["upgrade", "update", "migration", "version"],
    "guide": ["guide", "manual", "documentation", "instructions", "tutorial"],
}

# NEW: Problem/Issue detection for better troubleshooting support
ISSUE_SYNONYMS = {
    "problems": ["problem", "issue", "error", "trouble", "fail", "troubleshoot", "debug", "fix"],
    "issues": ["issue", "problem", "trouble", "error", "debug", "troubleshoot", "fix"],
    "errors": ["error", "exception", "failure", "issue", "problem", "debug", "troubleshoot"],
    "fails": ["failure", "error", "problem", "issue", "troubleshoot", "debug", "fix"],
    "trouble": ["trouble", "problem", "issue", "error", "troubleshoot", "debug"],
    "broken": ["broken", "error", "failure", "problem", "troubleshoot", "debug", "fix"],
}

# NEW: Context-aware expansion patterns
CONTEXT_PATTERNS = {
    "activation": {
        "base_terms": ["activation", "activate"],
        "problem_context": ["licensing", "key", "token", "troubleshoot", "debug"],
        "setup_context": ["installation", "configuration", "setup"],
    },
    "configuration": {
        "base_terms": ["configuration", "config", "configure"],
        "problem_context": ["troubleshoot", "debug", "error", "issue"],
        "setup_context": ["installation", "setup", "deployment"],
    },
}

# Extended security patterns for broader coverage
EXTENDED_SECURITY_PATTERNS = {
    "filename_patterns": [
        # Original patterns
        r".*security.*guide.*",
        r".*security.*manual.*",
        r".*hsm.*installation.*",
        r".*hardware.*security.*module.*",
        r".*security.*configuration.*",
        r".*encryption.*guide.*",
        r".*certificate.*management.*",
        r".*cryptographic.*",
        r".*key.*management.*",
        r".*authentication.*guide.*",
        r".*firewall.*configuration.*",
        r".*vpn.*setup.*",
        r".*ssl.*tls.*configuration.*",
        # NEW: Extended patterns
        r".*compliance.*audit.*",
        r".*regulatory.*requirements.*",
        r".*security.*standards.*",
        r".*threat.*assessment.*",
        r".*risk.*analysis.*",
        r".*vulnerability.*scan.*",
        r".*incident.*response.*",
        r".*penetration.*test.*",
        r".*security.*policy.*",
        r".*access.*control.*",
    ],
    "content_patterns": [
        # Original patterns
        r"hardware\s+security\s+module",
        r"hsm\s+installation",
        r"cryptographic\s+keys?",
        r"certificate\s+management",
        r"security\s+configuration",
        r"authentication\s+mechanisms?",
        r"encryption\s+standards?",
        r"security\s+protocols?",
        r"access\s+control\s+lists?",
        r"firewall\s+rules?",
        r"intrusion\s+detection",
        r"vulnerability\s+assessment",
        r"penetration\s+testing",
        r"security\s+audit",
        r"compliance\s+requirements?",
        r"security\s+best\s+practices?",
        # NEW: Extended patterns
        r"threat\s+modeling",
        r"risk\s+assessment",
        r"security\s+incident",
        r"data\s+protection",
        r"privacy\s+controls?",
        r"security\s+policies?",
        r"regulatory\s+compliance",
        r"security\s+framework",
        r"information\s+security",
        r"cybersecurity\s+",
        r"security\s+governance",
    ],
}


def enhanced_query_expansion(query: str) -> str:
    """Enhanced query expansion with problem detection and context awareness."""
    query_lower = query.lower()
    expanded_terms = [query]

    # 1. Product synonym expansion (existing)
    for product, synonyms in ENHANCED_PRODUCT_SYNONYMS.items():
        if any(term in query_lower for term in synonyms):
            for synonym in synonyms:
                if synonym not in query_lower:
                    expanded_terms.append(synonym)

    # 2. Enhanced problem/issue detection
    for issue_term, synonyms in ISSUE_SYNONYMS.items():
        if issue_term in query_lower:
            # Add support-related terms
            for synonym in synonyms[:3]:  # Top 3 most relevant
                if synonym not in query_lower:
                    expanded_terms.append(synonym)

    # 3. Context-aware expansion
    for context_term, patterns in CONTEXT_PATTERNS.items():
        if context_term in query_lower:
            # Detect if it's a problem context or setup context
            is_problem_context = any(
                problem_word in query_lower for problem_word in ["problem", "issue", "error", "fail", "trouble"]
            )

            if is_problem_context:
                # Add problem-solving terms
                for term in patterns["problem_context"][:2]:
                    if term not in query_lower:
                        expanded_terms.append(term)
            else:
                # Add setup-related terms
                for term in patterns["setup_context"][:2]:
                    if term not in query_lower:
                        expanded_terms.append(term)

    # 4. Domain-specific expansion (existing)
    for domain_term, expansions in ENHANCED_DOMAIN_EXPANSIONS.items():
        if domain_term in query_lower:
            for expansion in expansions[:2]:
                if expansion not in query_lower:
                    expanded_terms.append(expansion)

    # Create enhanced query (limit to prevent explosion)
    if len(expanded_terms) > 1:
        expanded_query = f"{query} {' '.join(expanded_terms[1:6])}"  # Original + top 5 expansions
        return expanded_query

    return query


def enhanced_security_classification(text: str, filename: str):
    """Enhanced security document classification with extended patterns."""
    filename_lower = filename.lower()
    text_lower = text.lower()

    # Check filename patterns (including new ones)
    for pattern in EXTENDED_SECURITY_PATTERNS["filename_patterns"]:
        if re.search(pattern, filename_lower):
            return {
                "document_type": "security_guide",
                "confidence": 0.95,
                "matched_pattern": pattern,
                "match_type": "filename",
            }

    # Check content patterns (including new ones)
    for pattern in EXTENDED_SECURITY_PATTERNS["content_patterns"]:
        if re.search(pattern, text_lower):
            return {
                "document_type": "security_guide",
                "confidence": 0.90,
                "matched_pattern": pattern,
                "match_type": "content",
            }

    return None


def test_phase2_improvements():
    """Test Phase 2 accuracy improvements."""
    print("🚀 PHASE 2 ACCURACY IMPROVEMENTS TEST")
    print("=" * 60)

    # Test enhanced query expansion
    print("\n🔍 Enhanced Query Expansion Tests:")
    test_queries = [
        "license activation problems",  # Previously failing case
        "FlexNet server configuration errors",
        "ESM authentication issues",
        "activation troubleshooting guide",
        "certificate installation failures",
        "RNI upgrade problems",
    ]

    expansion_successes = 0
    for i, query in enumerate(test_queries, 1):
        print(f"\nTest {i}: '{query}'")
        expanded = enhanced_query_expansion(query)

        # Check if problem-solving terms are included
        expanded_lower = expanded.lower()
        has_troubleshoot_terms = any(
            term in expanded_lower for term in ["troubleshoot", "debug", "error", "issue", "problem", "fix"]
        )

        if has_troubleshoot_terms and len(expanded.split()) > len(query.split()):
            print(f"✅ PASS: Enhanced expansion includes troubleshooting terms")
            print(f"   Expanded: '{expanded}'")
            expansion_successes += 1
        else:
            print(f"⚠️ LIMITED: Basic expansion")
            print(f"   Expanded: '{expanded}'")

    expansion_accuracy = (expansion_successes / len(test_queries)) * 100

    # Test extended security classification
    print(f"\n🔒 Extended Security Classification Tests:")
    security_tests = [
        {
            "filename": "Compliance_Audit_Report.pdf",
            "content": "Regulatory compliance audit findings and security framework assessment.",
            "description": "Compliance document (new pattern)",
        },
        {
            "filename": "Threat_Assessment_Analysis.pdf",
            "content": "Threat modeling and risk assessment for cybersecurity governance.",
            "description": "Threat assessment (new pattern)",
        },
        {
            "filename": "Data_Protection_Policy.pdf",
            "content": "Data protection controls and privacy compliance requirements.",
            "description": "Data protection policy (new pattern)",
        },
    ]

    security_successes = 0
    for i, test in enumerate(security_tests, 1):
        print(f"\nTest {i}: {test['description']}")
        print(f"File: {test['filename']}")

        result = enhanced_security_classification(test["content"], test["filename"])

        if result and result["document_type"] == "security_guide":
            print(f"✅ PASS: Correctly classified as security_guide")
            print(f"   Pattern: {result['matched_pattern']}")
            security_successes += 1
        else:
            print(f"❌ FAIL: Not classified as security document")

    security_accuracy = (security_successes / len(security_tests)) * 100

    # Calculate projected overall improvement
    print(f"\n📊 Phase 2 Improvement Results:")
    print(f"   Enhanced Query Expansion: {expansion_accuracy:.1f}% (vs 83.3% baseline)")
    print(f"   Extended Security Classification: {security_accuracy:.1f}% (new patterns)")

    # Project overall accuracy improvement
    query_weight = 0.35
    current_overall = 89.9

    query_improvement = (expansion_accuracy - 83.3) * query_weight
    projected_overall = current_overall + query_improvement

    print(f"\n🎯 Projected Overall Accuracy:")
    print(f"   Current: 89.9%")
    print(f"   With Phase 2A: {projected_overall:.1f}%")
    print(f"   Improvement: {projected_overall - current_overall:+.1f} percentage points")

    if projected_overall >= 93.0:
        print(f"   Status: ✅ TARGET 93%+ ACHIEVABLE")
    else:
        print(f"   Status: 📈 PROGRESS TOWARD 95% TARGET")

    return projected_overall


if __name__ == "__main__":
    projected_accuracy = test_phase2_improvements()
    print(f"\n{'='*60}")
    if projected_accuracy >= 93.0:
        print("🎉 PHASE 2A IMPROVEMENTS SHOW SIGNIFICANT POTENTIAL!")
    else:
        print("📈 PHASE 2A IMPROVEMENTS SHOW MEASURABLE GAINS")
    print(f"{'='*60}")
