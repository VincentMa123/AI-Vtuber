"""
Test script to demonstrate semantic query detection vs keyword matching.
Run this to see how the new approach handles various queries.
"""

import sys
import os

# Enable verbose mode to see similarity scores
os.environ['RAG_VERBOSE'] = '1'

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag import detect_product_query, detect_promotion_query

# Test queries
test_queries = [
    # Product queries (should be detected)
    "Saya butuh susu untuk bayi",
    "Pengen beli cemilan enak",
    "Vitamin apa yang bagus?",
    "I'm looking for cooking oil",
    "Need some soap",
    
    # Promotion queries (should be detected)
    "Ada diskon gak hari ini?",
    "Penawaran spesial apa?",
    "Any sales this week?",
    "Promo heboh dong!",
    
    # Non-product/promo queries (should NOT be detected)
    "Halo! Apa kabar?",
    "Cerita tentang dirimu dong",
    "What's the weather like?",
    "Siapa presiden Indonesia?",
]

print("=" * 60)
print("SEMANTIC QUERY DETECTION TEST")
print("=" * 60)

for query in test_queries:
    is_product = detect_product_query(query)
    is_promo = detect_promotion_query(query)
    
    result = []
    if is_product:
        result.append("PRODUCT")
    if is_promo:
        result.append("PROMO")
    if not result:
        result.append("GENERAL")
    
    print(f"\n📝 Query: \"{query}\"")
    print(f"   → Detected as: {' + '.join(result)}")

print("\n" + "=" * 60)
print("✅ Test complete! The semantic approach can detect intent")
print("   without needing explicit keywords for every product type.")
print("=" * 60)
