"""Phase 4 Quick Reference: Query Routing and Refusal Handling."""

# ============================================================================
# ROUTER: Classify query intent
# ============================================================================

from app.router import IntentRouter, QueryIntent

router = IntentRouter()

# Classification Examples
examples = {
    "What are the holdings?": QueryIntent.FACTUAL,
    "Should I invest?": QueryIntent.ADVISORY,
    "Compare these funds": QueryIntent.COMPARATIVE,
    "Will this fund go up?": QueryIntent.PREDICTIVE,
    "Tell me about funds": QueryIntent.AMBIGUOUS,
}

for query, expected_intent in examples.items():
    result = router.classify(query)
    print(f"{query:40} → {result.intent.value:12} (conf: {result.confidence:.1f})")
    print(f"  Matched patterns: {result.matched_patterns}\n")

# Check if should refuse
should_refuse, intent = router.should_refuse("Should I buy this fund?")
print(f"Refuse advisory query? {should_refuse} ({intent.value})")

# ============================================================================
# REFUSAL COMPOSER: Generate compliant refusal responses
# ============================================================================

from app.refusal import RefusalComposer

composer = RefusalComposer()

# Generate refusals by intent type
print("\n" + "=" * 70)
print("REFUSAL RESPONSES")
print("=" * 70)

intents_to_refuse = [
    QueryIntent.ADVISORY,
    QueryIntent.COMPARATIVE,
    QueryIntent.PREDICTIVE,
]

for intent in intents_to_refuse:
    response = composer.compose_refusal(intent, use_default_link=True)
    print(f"\n[{intent.value.upper()}]")
    print(response)
    print()

# ============================================================================
# POLICY ENFORCER: Validate responses for compliance
# ============================================================================

from app.refusal import PolicyEnforcer

enforcer = PolicyEnforcer()

# Test cases
test_responses = [
    ("This fund has good returns. See: https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
     "Valid: single approved URL"),
    ("See: https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth and https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
     "Invalid: multiple URLs"),
    ("This fund is interesting. Visit: https://example.com",
     "Invalid: non-approved URL"),
    ("The expense ratio is 0.5%",
     "Valid: no URL needed (factual)",),
]

print("\n" + "=" * 70)
print("POLICY VALIDATION")
print("=" * 70)

for response, description in test_responses:
    urls = enforcer.extract_urls(response)
    is_valid, reason = enforcer.validate_response(response, urls)
    print(f"\n{description}")
    print(f"Response: {response[:60]}...")
    print(f"URLs found: {urls}")
    print(f"Valid? {is_valid} ({reason})")

# ============================================================================
# FULL PIPELINE: Router → Refusal
# ============================================================================

print("\n" + "=" * 70)
print("FULL PIPELINE EXAMPLE")
print("=" * 70)

queries = [
    "What is the expense ratio of HDFC Equity Fund?",
    "Which fund should I invest in?",
    "Compare HDFC Equity with HDFC Small Cap",
    "Will HDFC Small Cap have good returns next year?",
]

for user_query in queries:
    print(f"\nUser: {user_query}")
    
    should_refuse, intent = router.should_refuse(user_query)
    
    if should_refuse:
        print(f"Decision: REFUSE ({intent.value})")
        response = composer.compose_refusal(intent, use_default_link=True)
        print(f"Response:\n{response}")
    else:
        print(f"Decision: PROCEED to retrieval ({intent.value})")
        print("Would continue to Phase 5 (Retrieval)...")

# ============================================================================
# INTEGRATION PATTERN
# ============================================================================

print("\n" + "=" * 70)
print("PHASE 4 → PHASE 5 INTEGRATION")
print("=" * 70)

def process_query_with_phase4(user_query):
    """Process query: route → refuse or retrieve."""
    
    # Phase 4: Route
    router = IntentRouter()
    should_refuse, intent = router.should_refuse(user_query)
    
    if should_refuse:
        # Generate refusal
        composer = RefusalComposer()
        response = composer.compose_refusal(intent)
        
        # Validate compliance
        enforcer = PolicyEnforcer()
        urls = enforcer.extract_urls(response)
        is_valid, reason = enforcer.validate_response(response, urls)
        
        if is_valid:
            return {"type": "refusal", "response": response}
        else:
            return {"type": "error", "reason": f"Refusal validation failed: {reason}"}
    else:
        # Phase 5: Retrieval (not implemented yet)
        return {"type": "retrieve", "query": user_query, "intent": intent.value}

# Test the integration
sample_query = "Should I invest in HDFC Equity Fund?"
result = process_query_with_phase4(sample_query)
print(f"\nQuery: {sample_query}")
print(f"Result: {result}")
print(f"\nResponse begins:\n{result['response'][:150]}...")
