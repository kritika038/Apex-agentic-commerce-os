from typing import List, Dict, Any, Optional
from app.ai.providers.base import LLMProvider
from app.schemas.ai import ChatMessage
import json
import re

class MockLLMProvider(LLMProvider):
    def generate_chat_response(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None
    ) -> ChatMessage:
        
        last_msg = messages[-1]
        
        # Check tool responses first
        if last_msg.role == "tool":
            tool_content = last_msg.content
            try:
                data = json.loads(tool_content)
                if "results" in data:
                    results = data["results"]
                    if len(results) > 1:
                        names = [f"**{r['name']}** (₹{int(r['price']):,})" for r in results[:3]]
                        summary_str = ", ".join(names[:-1]) + f", and {names[-1]}" if len(names) > 2 else " and ".join(names)
                        return ChatMessage(
                            role="assistant",
                            content=f"I found {len(results)} great matching options in our store catalog: {summary_str}. All options are in stock and verified against our real-time inventory. You can compare them and add them directly to your cart below."
                        )
                    elif len(results) == 1:
                        p = results[0]
                        return ChatMessage(
                            role="assistant",
                            content=f"I found **{p['name']}** for ₹{int(p['price']):,} in our {p['category']} collection. It is verified in stock ({p.get('stock_quantity', 1)} available) and ready to add to your cart."
                        )
                    else:
                        return ChatMessage(
                            role="assistant",
                            content="I searched our catalog but didn't find any products matching those specific constraints. Feel free to ask for running shoes, gym apparel, or workout accessories!"
                        )
                elif data.get("success"):
                    return ChatMessage(
                        role="assistant",
                        content=data.get("message", "Product has been successfully added to your cart.")
                    )
                elif "error" in data:
                    return ChatMessage(
                        role="assistant",
                        content=f"Could not complete the action: {data['error']}"
                    )
            except Exception:
                pass
            return ChatMessage(role="assistant", content="I have updated your shopping session.")

        last_text = last_msg.content.lower().strip()
        
        # Scenario: Malicious attempt to manipulate price
        if "ignore" in last_text or "set price" in last_text or "discount" in last_text or "price to" in last_text:
            return ChatMessage(
                role="assistant",
                content="I cannot alter or negotiate catalog prices. All pricing is determined authoritatively by the merchant store policies."
            )

        # Scenario: Add product to cart
        if "add" in last_text:
            qty = 1
            qty_match = re.search(r'\b(?:add|qty|quantity)\s+(\d+)\b', last_text)
            if qty_match:
                qty = int(qty_match.group(1))
            elif "1000" in last_text.split():
                qty = 1000
            
            product_id = "test_product_id"
            for word in last_msg.content.split():
                clean_word = word.strip(",.!?\"'")
                if clean_word.startswith("prod_") or clean_word.startswith("p_") or len(clean_word) == 36:
                    product_id = clean_word
                    break

            return ChatMessage(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": "call_mock_add",
                    "type": "function",
                    "function": {
                        "name": "add_to_cart",
                        "arguments": json.dumps({"product_id": product_id, "quantity": qty})
                    }
                }]
            )

        # Extract budget / max_price if present (e.g. "under 4000", "under ₹4,000", "< 5000", or standalone "400")
        max_p: Optional[float] = None
        price_match = re.search(r'(?:under|below|less than|within|max|<|<=)\s*(?:₹|rs\.?|inr)?\s*([0-9]+(?:,[0-9]+)?)', last_text)
        if price_match:
            try:
                max_p = float(price_match.group(1).replace(',', ''))
            except Exception:
                pass
        elif re.fullmatch(r'(?:₹|rs\.?|inr)?\s*([0-9]+(?:,[0-9]+)?)', last_text):
            try:
                max_p = float(re.sub(r'[^0-9.]', '', last_text))
            except Exception:
                pass

        # Scenario: Product discovery / search keywords
        query_kw = None
        category_kw = None
        
        if "running" in last_text or "shoe" in last_text or "sneaker" in last_text:
            category_kw = "Running"
        elif "sock" in last_text:
            query_kw = "Socks"
            category_kw = "Accessories"
        elif "bottle" in last_text or "water" in last_text or "flask" in last_text:
            query_kw = "Bottle"
            category_kw = "Accessories"
        elif "watch" in last_text or "tracker" in last_text or "gps" in last_text or "fitness" in last_text or "electronics" in last_text:
            category_kw = "Electronics"
        elif "bag" in last_text or "duffle" in last_text or "gym bag" in last_text:
            category_kw = "Bags"
        elif "shirt" in last_text or "tee" in last_text or "dry-fit" in last_text or "apparel" in last_text or "top" in last_text:
            category_kw = "Apparel"
        elif "short" in last_text or "shorts" in last_text:
            query_kw = "Shorts"
            category_kw = "Apparel"
        elif "gym" in last_text or "accessory" in last_text or "accessories" in last_text:
            category_kw = "Accessories"
        elif "setup" in last_text or "gear" in last_text or "training" in last_text or "marathon" in last_text:
            category_kw = "Running"
        elif any(k in last_text for k in ["what products", "show all", "all products", "catalog", "browse", "everything", "have?", "what do you have"]):
            # Broad catalog inquiry
            search_args = {}
            return ChatMessage(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": "call_search_catalog",
                    "type": "function",
                    "function": {
                        "name": "search_products",
                        "arguments": json.dumps(search_args)
                    }
                }]
            )
        elif "show" in last_text or "find" in last_text or "look" in last_text or "search" in last_text or "recommend" in last_text:
            # Extract search terms
            cleaned = re.sub(r'^(show me|find me|find|look for|search for|recommend|i need|i want|get me)\s*', '', last_text)
            query_kw = cleaned.split()[0] if cleaned.split() else "Running"

        if query_kw or category_kw or max_p:
            search_args = {}
            if query_kw:
                search_args["query"] = query_kw
            if category_kw:
                search_args["category"] = category_kw
            if max_p is not None:
                search_args["max_price"] = max_p
            return ChatMessage(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": "call_search_catalog",
                    "type": "function",
                    "function": {
                        "name": "search_products",
                        "arguments": json.dumps(search_args)
                    }
                }]
            )

        return ChatMessage(
            role="assistant",
            content="Hello! I am your AI Shopping Assistant for Apex Sports. I can help you discover running shoes, athletic apparel, gym gear, and fitness electronics tailored to your budget and workout routine. What are you shopping for today?"
        )
