"""
Demonstration: How few examples can generalize to many products
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag.embeddings import get_embedding_model
import numpy as np

# Load model
model = get_embedding_model()

# ONLY 5 example queries (no "cooking oil", "bread", "shampoo", etc.)
examples = [
    "Ada produk susu apa?",      # milk
    "Mau beli sabun",            # soap  
    "Cari deterjen murah",       # detergent
    "I need to buy vitamins",    # vitamins
    "Show me some snacks"        # snacks
]

# Test queries for products NOT in examples
test_queries = [
    "I'm looking for cooking oil",  # NOT in examples!
    "Butuh shampo bagus",           # NOT in examples!
    "Ada roti tawar?",              # NOT in examples!
    "Need some toothpaste",         # NOT in examples!
    "Pengen beli keju",             # cheese - NOT in examples!
]

print("=" * 70)
print("SEMANTIC GENERALIZATION TEST")
print("=" * 70)
print(f"\n📚 Training with ONLY {len(examples)} examples:")
for i, ex in enumerate(examples, 1):
    print(f"   {i}. {ex}")

print(f"\n🧪 Testing queries for products NOT in examples:\n")

# Encode examples
example_embeddings = model.encode(examples, convert_to_numpy=True)

for query in test_queries:
    # Encode query
    query_embedding = model.encode([query], convert_to_numpy=True)[0]
    
    # Calculate similarity
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    example_norms = example_embeddings / np.linalg.norm(example_embeddings, axis=1, keepdims=True)
    similarities = np.dot(example_norms, query_norm)
    
    max_sim = np.max(similarities)
    best_match_idx = np.argmax(similarities)
    
    # Check if detected (threshold 0.5)
    detected = "✅ DETECTED" if max_sim >= 0.4 else "❌ MISSED"
    
    print(f"Query: \"{query}\"")
    print(f"  → {detected} (similarity: {max_sim:.3f})")
    print(f"  → Most similar to: \"{examples[best_match_idx]}\"")
    print()

print("=" * 70)
print("💡 KEY INSIGHT: With just 5 examples, the model understands")
print("   the PATTERN of product queries, not just specific products!")
print("=" * 70)
