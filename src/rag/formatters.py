from typing import List, Dict


def format_products_for_prompt(products: List[Dict]) -> str:

    if not products:
        return ""
    
    formatted = "\n## Product Reference (DO NOT copy this format - use natural speech):\n"
    
    for i, product in enumerate(products, 1):
        name = product.get("name", "Unknown Product")
        price = product.get("price", 0)
        description = product.get("description", "")
        
        price_formatted = f"Rp {price:,}"
        
        formatted += f"- {name}: {price_formatted}\n"
        if description:
            formatted += f"  ({description})\n"
    
    formatted += "\n[IMPORTANT: Mention products conversationally, e.g. 'Coba Wong Coco, enak dan murah!' - NEVER copy the format above]\n"
    
    return formatted


def format_promotions_for_prompt(promotions: List[Dict]) -> str:

    if not promotions:
        return ""
    
    formatted = "\n## Current Indomaret Promotions:\n"
    
    for i, promo in enumerate(promotions, 1):
        promo_type = promo.get("type", "Unknown Promo")
        description = promo.get("description", "")
        time_range = promo.get("time_range", "")
        
        formatted += f"{i}. {promo_type}"
        if time_range:
            formatted += f" ({time_range})"
        formatted += f"\n   {description}\n"
    
    formatted += "\nShare these promotions naturally with viewers!\n"
    
    return formatted
