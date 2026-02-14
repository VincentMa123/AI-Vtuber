"""
Simple Product Info Extractor
Works directly with JSON response - no API calls needed
"""

import json


def extract_and_display_products(json_response):
    """
    Extract and display products from search response
    
    Args:
        json_response: The full JSON response from the API (as dict or string)
    """
    # If it's a string, parse it
    if isinstance(json_response, str):
        data = json.loads(json_response)
    else:
        data = json_response
    
    # Get products array
    products = data.get('data', {}).get('content', [])
    total = data.get('data', {}).get('totalElements', 0)
    
    print("=" * 100)
    print(f"📊 SEARCH RESULTS: {len(products)} products shown (Total: {total})")
    print("=" * 100)
    
    for i, product in enumerate(products, 1):
        print(f"\n{'─' * 100}")
        print(f"#{i}. {product.get('productName', 'Unknown Product')}")
        print(f"{'─' * 100}")
        
        # Basic Info
        print(f"🏷️  Brand: {product.get('brandName', 'N/A')}")
        print(f"📏 Size: {product.get('size', 'N/A')}")
        print(f"🔗 Product ID: {product.get('plu', 'N/A')}")
        
        # Price Info
        price = product.get('price', 0)
        final_price = product.get('finalPrice')
        
        if final_price:
            discount = price - final_price
            discount_pct = (discount / price * 100) if price > 0 else 0
            print(f"\n💰 Original Price: Rp {price:,}")
            print(f"🎯 Final Price: Rp {final_price:,}")
            print(f"💵 You Save: Rp {discount:,} ({discount_pct:.1f}% OFF)")
            if product.get('discountText'):
                print(f"🏷️  Discount Tag: {product.get('discountText')}")
        else:
            print(f"\n💰 Price: Rp {price:,}")
        
        # Promo
        if product.get('promoText'):
            print(f"\n🎁 Promo: {product.get('promoText')}")
        
        # Descriptions
        descriptions = product.get('descriptionList', [])
        if descriptions:
            print(f"\n📝 Product Details:")
            for desc in descriptions:
                title = desc.get('title', 'Info')
                content = desc.get('content', '')
                
                # Only show important descriptions, truncate if too long
                if title in ['Deskripsi Produk', 'Other Details', 'Komposisi', 'BPOM RI', 'Halal']:
                    if len(content) > 150:
                        content = content[:150] + "..."
                    print(f"   • {title}: {content}")
        
        # Product URL
        permalink = product.get('permalink', '')
        if permalink:
            print(f"\n🔗 URL: https://www.klikindomaret.com/product/{permalink}")
        
        # Image
        if product.get('imageUrl'):
            print(f"📸 Image: {product.get('imageUrl')}")
        
        # Availability
        if product.get('selling'):
            print(f"✅ Available for purchase")
        else:
            print(f"❌ Not available")


def create_simple_summary(json_response):
    """Create a simple list of products with key info"""
    if isinstance(json_response, str):
        data = json.loads(json_response)
    else:
        data = json_response
    
    products = data.get('data', {}).get('content', [])
    
    print("\n" + "=" * 100)
    print("📋 SIMPLE SUMMARY")
    print("=" * 100)
    
    for i, p in enumerate(products, 1):
        price = p.get('price', 0)
        final = p.get('finalPrice', price)
        
        print(f"{i:2}. {p.get('productName', 'Unknown'):<50} ", end="")
        print(f"Rp {final:>8,} ", end="")
        
        if final < price:
            discount = ((price - final) / price * 100)
            print(f"(-{discount:.0f}%)", end="")
        
        print()


def save_to_simple_text(json_response, filename="products_summary.txt"):
    """Save products to a simple text file"""
    if isinstance(json_response, str):
        data = json.loads(json_response)
    else:
        data = json_response
    
    products = data.get('data', {}).get('content', [])
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("KLIKINDOMARET SEARCH RESULTS\n")
        f.write("=" * 80 + "\n\n")
        
        for i, p in enumerate(products, 1):
            f.write(f"{i}. {p.get('productName', 'Unknown')}\n")
            f.write(f"   Brand: {p.get('brandName', 'N/A')} | Size: {p.get('size', 'N/A')}\n")
            
            price = p.get('price', 0)
            final = p.get('finalPrice', price)
            
            if final < price:
                f.write(f"   Price: Rp {price:,} → Rp {final:,}\n")
            else:
                f.write(f"   Price: Rp {price:,}\n")
            
            # Main description
            descs = p.get('descriptionList', [])
            for desc in descs:
                if desc.get('title') == 'Deskripsi Produk':
                    content = desc.get('content', '')[:200]
                    f.write(f"   Description: {content}\n")
                    break
            
            f.write("\n")
    
    print(f"\n✓ Saved to {filename}")


# Example usage
if __name__ == "__main__":
    # You can paste your JSON response here
    # Or load from a file
    
    import sys
    
    if len(sys.argv) > 1:
        # Load from file
        filename = sys.argv[1]
        print(f"Loading from {filename}...")
        with open(filename, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    else:
        # Example: Use the sample data you provided
        print("Paste your JSON response (press Ctrl+D or Ctrl+Z when done):")
        print("Or save your JSON to a file and run: python product_extractor_simple.py yourfile.json")
        print("-" * 80)
        
        try:
            json_text = sys.stdin.read()
            json_data = json.loads(json_text)
        except:
            print("\n❌ Invalid JSON or no input provided")
            print("\nAlternatively, edit this script and paste your JSON response in the code")
            exit(1)
    
    # Display products
    extract_and_display_products(json_data)
    
    # Simple summary
    create_simple_summary(json_data)
    
    # Save option
    save = input("\nSave to text file? (y/n): ").strip().lower()
    if save == 'y':
        save_to_simple_text(json_data)