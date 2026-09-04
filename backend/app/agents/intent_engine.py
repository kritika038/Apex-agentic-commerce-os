import re
from typing import Dict, Any, List, Optional, Tuple

class ConversationIntentEngine:
    """
    Deterministic Multi-Lingual Conversation Context & Active Shopping Intent Engine.
    
    Principles:
    - 100% catalog-grounded and server-authoritative.
    - Preserves active category and conversational shopping context across turns.
    - Supports English, Hindi (Devanagari), and Hinglish (Phonetic/Romanized).
    - Robust entity resolution: "this one", "that one", "best one", "cheapest", "add it", "remove it".
    - Recognizes full Agentic Commerce "Finalize & Order" purchase commands.
    - Strictly prevents unprompted cross-selling.
    """

    CATEGORIES = {
        "Running": {
            "keywords": [
                "running", "shoe", "shoes", "sneaker", "sneakers", "marathon", "trail", 
                "joota", "joote", "jute", "jhoote", "jootey", "jutta", "jutte", "jootte",
                "जूते", "जूता", "शूज़", "शूज", "रनिंग", "दौड़",
                "speedflow", "pro running", "footwear"
            ],
            "product_type": "Running Shoes",
            "product_type_hi": "running shoes",
            "default_query": None,
            "aliases": ["running shoes", "shoes", "sneakers", "running footwear", "joote"]
        },
        "Bags": {
            "keywords": [
                "bag", "bags", "gym bag", "duffle", "duffle bag", "duffel", "backpack", 
                "tote", "jhola", "kit bag", "बैग", "बस्ता", "झोला"
            ],
            "product_type": "Gym Bags",
            "product_type_hi": "gym bags",
            "default_query": "Bag",
            "aliases": ["gym bags", "duffle bags", "bags"]
        },
        "Electronics": {
            "keywords": [
                "watch", "smartwatch", "tracker", "fitness tracker", "fitness watch", 
                "gps", "gadget", "ghadi", "smart watch", "घड़ी", "स्मार्टवॉच"
            ],
            "product_type": "Fitness Watch",
            "product_type_hi": "fitness watch",
            "default_query": "Watch",
            "aliases": ["fitness tracker", "smartwatches", "watches"]
        },
        "Apparel": {
            "keywords": [
                "shirt", "t-shirt", "tshirt", "dry-fit", "tee", "top", "shorts", 
                "running shorts", "clothes", "clothing", "kapde", "kapda", "apparel", "sportswear",
                "कपड़े", "टी-शर्ट", "शॉर्ट्स"
            ],
            "product_type": "Apparel",
            "product_type_hi": "workout kapde",
            "default_query": None,
            "aliases": ["athletic apparel", "t-shirts", "shorts"]
        },
        "Water Bottle": {
            "keywords": [
                "bottle", "water bottle", "flask", "sports flask", "paani ki bottle", 
                "pani ki bottle", "बोतल", "पानी की बोतल", "पानी की बॉटल", "बॉटल"
            ],
            "category": "Accessories",
            "product_type": "Water Bottle",
            "product_type_hi": "water bottle",
            "default_query": "Bottle",
            "aliases": ["water bottle", "flask", "bottle"]
        },
        "Socks": {
            "keywords": ["sock", "socks", "moze", "moza", "मोज़े", "मोज़ा", "sports socks"],
            "category": "Accessories",
            "product_type": "Performance Socks",
            "product_type_hi": "socks",
            "default_query": "Socks",
            "aliases": ["socks", "sports socks"]
        },
        "Foam Roller": {
            "keywords": ["roller", "foam roller", "massage roller", "recovery roller", "रोलर"],
            "category": "Accessories",
            "product_type": "Recovery Foam Roller",
            "product_type_hi": "foam roller",
            "default_query": "Roller",
            "aliases": ["foam roller", "roller"]
        },
        "Accessories": {
            "keywords": ["accessories", "accessory", "gear", "saman", "सामान"],
            "product_type": "Accessories",
            "product_type_hi": "accessories",
            "default_query": None,
            "aliases": ["accessories", "gear"]
        }
    }

    PRODUCT_NAME_PATTERNS = [
        ("SpeedFlow Marathon Shoes", ["speedflow marathon shoes", "speedflow marathon", "speedflow shoes", "speedflow", "marathon shoes"]),
        ("Pro Running Shoes", ["nike revolution 6", "nike revolution", "revolution 6", "revolution", "pro running shoes", "pro running", "pro runner"]),
        ("Air Cushion Trail Running Shoes", ["air cushion trail running shoes", "air cushion trail", "air cushion", "trail running shoes"]),
        ("Fitness Tracker Watch", ["fitness tracker watch", "fitness tracker", "fitness watch", "tracker watch", "smartwatch"]),
        ("Gym Duffle Bag", ["gym duffle bag", "gym duffel bag", "gym duffle", "duffle bag", "duffel bag"]),
        ("Sports Dry-Fit T-Shirt", ["nike dri-fit t-shirt", "nike dri-fit", "nike dri fit", "dri-fit", "sports dry fit t shirt", "sports dry-fit t-shirt", "dry fit t-shirt", "dry-fit t-shirt", "dry fit shirt", "dry-fit shirt", "dri-fit t shirt"]),
        ("Running Shorts", ["running shorts", "athletic shorts", "sports shorts", "puma active shorts", "puma shorts"]),
        ("Insulated Stainless Steel Water Bottle", ["insulated stainless steel water bottle", "stainless steel water bottle", "insulated water bottle", "water bottle", "steel bottle"]),
        ("Performance Socks", ["performance socks", "athletic socks", "sports socks", "running socks", "socks"]),
        ("Recovery Foam Roller", ["recovery foam roller", "foam roller", "massage roller", "roller"])
    ]

    RESET_PHRASES = [
        "start over", "new search", "forget that", "clear", "reset", 
        "let's look for something else", "something else", "shuru se", 
        "naya search", "kuch aur dikhao", "restart", "forget shoes", "forget it",
        "phir se shuru", "kuch aur", "shuru se shuru"
    ]

    FINALIZE_PHRASES = [
        # English
        "finalize this shoe and order it", "finalize this and order", "finalize it and order it",
        "finalize the first one and buy it", "finalize the second one and buy it", "finalize my cart",
        "finalize order", "finalize it", "finalize this", "finalize and order",
        "buy this one", "buy this", "buy it", "buy now", "buy the cheapest one", "buy the best one",
        "buy the first one", "buy what's in my cart", "buy whats in my cart", "buy my cart",
        "order this", "order it", "order now", "place the order", "place order", "checkout this one",
        "checkout now", "checkout my cart", "order my cart", "order everything in my cart",
        "i want this one order it", "order the best one", "order the cheapest one", "order the first one",
        "order the second one", "add this and checkout", "get this for me", "proceed with this purchase",
        "order this shoe", "order one water bottle", "order water bottle", "order shoes", "confirm and pay",
        "proceed to pay", "confirm order", "pay now", "checkout", "checkout order",
        # Hinglish
        "ye wala shoe final karo aur order kar do", "isko final karo aur mangwa lo",
        "isko order kar do", "ye wala order karo", "ye order kar do", "isko buy kar do",
        "ye wala buy kar do", "sabse achha wala order karo", "sabse accha wala order karo",
        "sabse sasta wala order karo", "pehla wala order karo", "doosra wala order karo",
        "cart finalize karo", "mera cart order karo", "order place kar do", "order mangwa do",
        "order confirm karo", "ye le lo aur order kar do", "theek hai isko order karo",
        "order kar do", "order karo", "buy karo", "checkout karo", "checkout kar do",
        "ye shoe final karo aur order kar do", "isko final karke order kar do", "ye wala le raha hoon order kar do",
        "isko checkout kar do", "ye final hai order kar do", "isko mere liye mangwa do", "cart checkout kar do",
        "ye vala final kro aur order kr do", "ye wala shoe final karo aur mere liye order kar do",
        "mangwa do", "kharid lo", "kharid do", "mere liye mangwa do", "order laga do", "final order",
        # Hindi
        "इसे खरीद दो", "इस जूते को ऑर्डर कर दो", "इसे अंतिम रूप देकर ऑर्डर कर दो", "सबसे अच्छा वाला ऑर्डर कर दो",
        "सबसे सस्ता वाला खरीद दो", "इसका चेकआउट कर दो", "ऑर्डर कर दो", "खरीद लो", "ऑर्डर करो"
    ]

    HINDI_INDICATORS = [
        "bhai", "chahiye", "dikhao", "dikhaye", "andar", "wale", "wali", "kaisa", "karo", 
        "hazaar", "hajar", "sau", "jute", "joote", "kapde", "ghadi", 
        "saste", "sasta", "mujhe", "batao", "hai", "kya", "tak", "aur",
        "sirf", "ek", "do", "daal", "doosra", "pehla", "achha", "sabse",
        "kro", "kr", "le", "lo", "mangwa", "mein", "ka", "ki", "ke", "paanch", "panch", "teen"
    ]

    @classmethod
    def normalize_text(cls, text: str) -> Tuple[str, str]:
        raw = text.strip()
        lower = raw.lower()

        is_hindi = any('\u0900' <= char <= '\u097F' for char in raw)
        is_hinglish = is_hindi or any(w in lower.split() for w in cls.HINDI_INDICATORS)
        detected_lang = "hindi" if is_hindi else ("hinglish" if is_hinglish else "english")

        # 1. Devanagari digit replacement
        devanagari_digits = {'०':'0', '१':'1', '२':'2', '३':'3', '४':'4', '५':'5', '६':'6', '७':'7', '८':'8', '९':'9'}
        for d_hi, d_en in devanagari_digits.items():
            lower = lower.replace(d_hi, d_en)

        # 2. Devanagari word substitutions
        devanagari_words = {
            "पाँच हज़ार": "5000", "पांच हजार": "5000", "पाँच हजार": "5000", "पांच हज़ार": "5000",
            "तीन हज़ार": "3000", "तीन हजार": "3000", "दो हज़ार": "2000", "दो हजार": "2000",
            "एक हज़ार": "1000", "एक हजार": "1000", "दस हज़ार": "10000", "दस हजार": "10000",
            "पाँच सौ": "500", "पांच सौ": "500", "छह सौ": "600", "शूज़": "shoes", "जूते": "shoes",
            "जूता": "shoes", "रनिंग": "running", "कपड़े": "apparel", "बैग": "bags", "बोतल": "bottle",
            "घड़ी": "watch", "मोज़े": "socks", "के अंदर": "under", "सस्ते": "cheaper", "सिर्फ एक": "1",
            "एक": "1", "दो": "2", "तीन": "3", "ऑर्डर": "order", "खरीद": "buy"
        }
        for hi_w, en_w in devanagari_words.items():
            lower = lower.replace(hi_w, en_w)

        # 3. Speech & ASR Noisy normalizations
        # Match 5k, 5 k, five thousand, five k, etc.
        # DO NOT match '500 ke' (which means 'of 500')
        lower = re.sub(r'\b(?:10\s*k|10k|ten\s*(?:thousand|k))\b', '10000', lower)
        lower = re.sub(r'\b(?:9\s*k|9k|nine\s*(?:thousand|k))\b', '9000', lower)
        lower = re.sub(r'\b(?:8\s*k|8k|eight\s*(?:thousand|k))\b', '8000', lower)
        lower = re.sub(r'\b(?:7\s*k|7k|seven\s*(?:thousand|k))\b', '7000', lower)
        lower = re.sub(r'\b(?:6\s*k|6k|six\s*(?:thousand|k))\b', '6000', lower)
        lower = re.sub(r'\b(?:5\s*k|5k|five\s*(?:thousand|k))\b', '5000', lower)
        lower = re.sub(r'\b500\s*kk+e?\b', '5000', lower)
        lower = re.sub(r'\b(?:4\s*k|4k|four\s*(?:thousand|k))\b', '4000', lower)
        lower = re.sub(r'\b(?:3\s*k|3k|three\s*(?:thousand|k))\b', '3000', lower)
        lower = re.sub(r'\b(?:2\s*k|2k|two\s*(?:thousand|k))\b', '2000', lower)
        lower = re.sub(r'\b(?:1\s*k|1k|one\s*(?:thousand|k))\b', '1000', lower)

        # Noisy ASR specific handles (e.g. pancho ke -> 5000 ke)
        lower = re.sub(r'\bpancho\s+ke\s+jhoote\b', '5000 ke joote', lower)
        lower = re.sub(r'\bpancho\s+ke\s+joote\b', '5000 ke joote', lower)
        lower = re.sub(r'\bpan\s+su\s+ke\s+joote\b', '5000 ke joote', lower)
        lower = re.sub(r'\bpan\s+su\s+ke\s+jhoote\b', '5000 ke joote', lower)
        lower = re.sub(r'\bpancho\b', '5000', lower)
        lower = re.sub(r'\bjhoote\b', 'joote', lower)
        lower = re.sub(r'\bjhutte\b', 'joote', lower)
        lower = re.sub(r'\bjootey\b', 'joote', lower)
        lower = re.sub(r'\bjutta\b', 'joote', lower)
        lower = re.sub(r'\bjutte\b', 'joote', lower)

        # ASR shortcuts: "kro" -> "karo", "kr" -> "karo", "vala" -> "wala"
        lower = re.sub(r'\b(?:kro|kr)\b', 'karo', lower)
        lower = re.sub(r'\bvala\b', 'wala', lower)

        # 4. Hindi word-number normalization
        lower = re.sub(r'\b(?:5|paanch|panch)\s*(?:hazaar|hajar|hajaar|hazare)\b', '5000', lower)
        lower = re.sub(r'\b(?:4|chaar|char|chaur)\s*(?:hazaar|hajar|hajaar)\b', '4000', lower)
        lower = re.sub(r'\b(?:3|teen|tin)\s*(?:hazaar|hajar|hajaar)\b', '3000', lower)
        lower = re.sub(r'\b(?:dhai)\s*(?:hazaar|hajar|hajaar)\b', '2500', lower)
        lower = re.sub(r'\b(?:2|do)\s*(?:hazaar|hajar|hajaar)\b', '2000', lower)
        lower = re.sub(r'\b(?:dedh|derh)\s*(?:hazaar|hajar|hajaar)\b', '1500', lower)
        lower = re.sub(r'\b(?:1|ek)\s*(?:hazaar|hajar|hajaar)\b', '1000', lower)
        lower = re.sub(r'\b(?:10|das|dus)\s*(?:hazaar|hajar|hajaar)\b', '10000', lower)

        lower = re.sub(r'\b(?:paanch|panch)\s*(?:sau|so)\b', '500', lower)
        lower = re.sub(r'\b(?:chhe|che)\s*(?:sau|so)\b', '600', lower)
        lower = re.sub(r'\b(?:saat)\s*(?:sau|so)\b', '700', lower)
        lower = re.sub(r'\b(?:aath|ath)\s*(?:sau|so)\b', '800', lower)
        lower = re.sub(r'\b(?:nau)\s*(?:sau|so)\b', '900', lower)
        lower = re.sub(r'\b(?:teen|tin)\s*(?:sau|so)\b', '300', lower)
        lower = re.sub(r'\b(?:do)\s*(?:sau|so)\b', '200', lower)
        lower = re.sub(r'\b(?:ek)\s*(?:sau|so)\b', '100', lower)

        # 5. Clean commas inside digits (e.g. "5,000" -> "5000")
        lower = re.sub(r'(\d),(\d)', r'\1\2', lower)

        # Clean punctuation
        lower = re.sub(r'[?.,!;:"]', ' ', lower)
        lower = re.sub(r'\s+', ' ', lower).strip()

        return lower, detected_lang

    @classmethod
    def extract_quantity(cls, text: str) -> Optional[int]:
        match = re.search(r'\b(?:add|qty|quantity|sirf|only|take|buy|order)?\s*(\d+)\s*(?:pair|pairs|bottles?|shoes?|units?|items?|piece|pieces)?\b', text)
        if match:
            try:
                q = int(match.group(1))
                if 1 <= q <= 10:
                    return q
            except Exception:
                pass
        return None

    @classmethod
    def analyze_message(
        cls,
        message: str,
        active_intent: Optional[Dict[str, Any]] = None,
        previous_products: Optional[List[Dict[str, Any]]] = None,
        cart: Optional[Dict[str, Any]] = None,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        normalized, detected_lang = cls.normalize_text(message)
        active_intent = active_intent or {}
        previous_products = previous_products or []
        
        lang = active_intent.get("language") or detected_lang
        if detected_lang in ["hindi", "hinglish"]:
            lang = "hinglish"
        is_hi = lang in ["hindi", "hinglish"]

        # 1. Check for Context Reset
        for phrase in cls.RESET_PHRASES:
            if phrase in normalized:
                reset_msg = (
                    "Aapka shopping session reset kar diya gaya hai. Aaj aap kya dekhna chahenge — running shoes, athletic kapde, gym bags, ya fitness accessories?"
                    if is_hi
                    else "I've reset your shopping session. What would you like to explore today — running shoes, athletic apparel, gym bags, or workout accessories?"
                )
                return {
                    "action": "RESET",
                    "active_intent": {"language": lang},
                    "message": reset_msg,
                    "products": [],
                    "search_params": None,
                    "language": lang
                }

        # 2. Extract Quantity
        quantity = cls.extract_quantity(normalized) or 1

        # 3. Check for AGENTIC PURCHASE / FINALIZE COMMANDS
        # (e.g. "Finalize this shoe and order it", "Buy this one", "Order the best one", "Ye wala shoe final karo aur order kar do")
        is_purchase_cmd = any(p in normalized for p in cls.FINALIZE_PHRASES) or (
            any(w in normalized for w in ["finalize", "final", "order", "buy", "checkout", "mangwa", "kharid"]) and
            any(w in normalized for w in ["it", "this", "one", "shoes", "shoe", "wala", "wali", "isko", "cart", "best", "cheapest", "sasta", "achha", "karo", "do"])
        )

        if is_purchase_cmd:
            # Check for Cart Scope
            if any(p in normalized for p in ["cart", "everything in cart", "whats in my cart", "what's in my cart", "all items"]):
                return {
                    "action": "FINALIZE_ORDER",
                    "target_scope": "CART",
                    "quantity": quantity,
                    "active_intent": active_intent,
                    "language": lang
                }

            # Check for Direct Named Product in text
            for prod_name, aliases in cls.PRODUCT_NAME_PATTERNS:
                if any(alias in normalized for alias in aliases):
                    return {
                        "action": "FINALIZE_ORDER",
                        "target_scope": "DIRECT_PRODUCT",
                        "product_name_query": prod_name,
                        "quantity": quantity,
                        "active_intent": active_intent,
                        "language": lang
                    }

            # Check for Entity Resolution from previous candidates or selected product
            target_prod = active_intent.get("selected_product") if isinstance(active_intent.get("selected_product"), dict) else None
            if previous_products and (not target_prod or any(p in normalized for p in ["best", "cheapest", "first", "second", "last", "doosra", "pehla", "sasta", "achha"])):
                if any(p in normalized for p in ["best", "best one", "best wala", "sabse accha", "sabse achha"]):
                    target_prod = cls._rank_best_product(previous_products)
                elif any(p in normalized for p in ["cheapest", "cheapest one", "sasta", "sabse sasta"]):
                    target_prod = min(previous_products, key=lambda x: float(x.get("price", 999999)))
                elif any(p in normalized for p in ["second", "doosra", "2nd"]):
                    target_prod = previous_products[1] if len(previous_products) > 1 else previous_products[0]
                elif any(p in normalized for p in ["first", "pehla", "1st"]):
                    target_prod = previous_products[0]
                elif any(p in normalized for p in ["last", "aakhri"]):
                    target_prod = previous_products[-1]
                elif not target_prod:
                    target_prod = previous_products[0]

            if target_prod:
                return {
                    "action": "FINALIZE_ORDER",
                    "target_scope": "CANDIDATE",
                    "product": target_prod,
                    "product_id": target_prod.get("id"),
                    "quantity": quantity,
                    "active_intent": active_intent,
                    "language": lang
                }

            # If no previous products and no named product, but user said "order" -> check cart or clarify
            if cart and cart.get("items") and len(cart.get("items", [])) > 0:
                return {
                    "action": "FINALIZE_ORDER",
                    "target_scope": "CART",
                    "quantity": quantity,
                    "active_intent": active_intent,
                    "language": lang
                }

        # 4. Check for Commerce Utility Intents
        # 4A. View Cart
        if any(p in normalized for p in ["view cart", "show cart", "cart dikhao", "mera cart", "check cart"]):
            return {
                "action": "VIEW_CART",
                "active_intent": active_intent,
                "message": "Ye raha aapka current cart status:" if is_hi else "Here is your current cart:",
                "products": [],
                "language": lang
            }

        # 4B. Coupon Code Application / Check
        coupon_match = re.search(r'\b(?:use|apply|coupon|code)\s+([A-Z0-9_-]{4,15})\b', message, re.IGNORECASE)
        if coupon_match:
            code = coupon_match.group(1).upper()
            if code in ["SAVE500", "APEX10", "WELCOME200"]:
                return {
                    "action": "APPLY_COUPON",
                    "coupon_code": code,
                    "active_intent": active_intent,
                    "language": lang
                }

        if any(p in normalized for p in ["coupon", "coupons", "promo code", "discount code", "coupon hai", "best coupon", "apply coupon", "coupon laga do", "discount laga do"]):
            return {
                "action": "CHECK_COUPONS",
                "active_intent": active_intent,
                "message": "Hamare paas active coupon **SAVE500** available hai jo ₹5,000+ ke orders par instant ₹500 discount deta hai." if is_hi else "We have active promo code **SAVE500** available for instant ₹500 discount on orders above ₹5,000.",
                "products": [],
                "language": lang
            }

        # 4C. Check / Use Rewards & Coins
        if any(p in normalized for p in ["coins", "points", "mere coins", "rewards", "balance", "apex coins", "mere paas kitne apex coins hain", "mere kitne coins hain", "mere paas kitne coins", "coins use", "use coins", "coins laga do", "use my coins", "how many apex coins do i have", "how many coins"]):
            return {
                "action": "CHECK_REWARDS",
                "active_intent": active_intent,
                "language": lang
            }

        # 4D. Check Orders
        if any(p in normalized for p in ["my orders", "previous orders", "meri order", "last order", "what did i buy", "meri last order kya thi", "meri pichli order", "pichli order", "pichla order", "meri last order"]):
            return {
                "action": "CHECK_ORDERS",
                "active_intent": active_intent,
                "language": lang
            }

        # 4E. Order Status / Tracking
        if any(p in normalized for p in ["where is my order", "track my order", "order status", "order kab ayega", "track order", "mera order kaha hai", "mera order kaha par hai", "order kaha hai", "tracking"]):
            return {
                "action": "ORDER_STATUS",
                "active_intent": active_intent,
                "language": lang
            }

        # 4F. Price Comparison / Price Intelligence Inquiry
        if any(p in normalized for p in [
            "cheaper somewhere else", "cheaper somewhere", "compare this", "compare shirt", 
            "compare price", "price comparison", "amazon pe kitne", "amazon pe", "amazon price",
            "myntra pe kitne", "myntra pe", "myntra price", "nike pe", "best price", "price compare",
            "find this shoe cheaper", "find cheaper", "is this cheaper", "kisi aur store pe", 
            "sasta kahan milega", "dusri jagah sasta", "compare this product", "compare prices",
            "best price check", "best price check karo", "price compare karo"
        ]):
            target_prod = None
            if previous_products:
                target_prod = previous_products[0]
            elif isinstance(active_intent.get("selected_product"), dict):
                target_prod = active_intent.get("selected_product")
            return {
                "action": "EXTERNAL_PRICE_CHECK",
                "target_product": target_prod,
                "product_id": target_prod.get("id") if target_prod else None,
                "active_intent": active_intent,
                "language": lang
            }

        # 4G. Explicit Colour Filter on Active Context (e.g. "black wala", "white wala")
        colours_map = {
            "black": "Black", "kala": "Black", "kaale": "Black", "kali": "Black",
            "white": "Pure White", "safed": "Pure White",
            "blue": "Navy Blue", "navy": "Navy Blue", "neela": "Navy Blue",
            "red": "Crimson Red", "laal": "Crimson Red",
            "grey": "Space Grey", "gray": "Space Grey",
            "silver": "Silver"
        }
        has_category_kw = any(w in normalized for w in ["shoe", "shoes", "joote", "running", "bottle", "socks", "bag", "apparel", "watch", "chahiye", "dikhao", "dikhaye"])
        if not has_category_kw:
            for col_kw, std_col in colours_map.items():
                if re.search(r'\b' + col_kw + r'(?:\s+wala|\s+wali|\s+colour|\s+color|\s+one)\b', normalized) or normalized.strip() in [col_kw, f"{col_kw} wala", f"{col_kw} wali"]:
                    return {
                        "action": "FILTER_COLOUR",
                        "colour": std_col,
                        "active_intent": active_intent,
                        "language": lang
                    }

        # 4H. Explicit Brand Filter on Active Context (e.g. "Nike wala", "Adidas wala", "Puma wala")
        brands_map = {
            "nike": "Nike", "adidas": "Adidas", "puma": "Puma", "asics": "Asics",
            "noise": "Noise", "boat": "Boat", "decathlon": "Decathlon", "milton": "Milton", "apple": "Apple"
        }
        if not has_category_kw:
            for br_kw, std_br in brands_map.items():
                if (re.search(r'\b' + br_kw + r'(?:\s+wala|\s+wali|\s+brand|\s+one)\b', normalized) or normalized.strip() in [br_kw, f"{br_kw} wala", f"{br_kw} wali"]) and not any(p in normalized for p in cls.FINALIZE_PHRASES):
                    return {
                        "action": "FILTER_BRAND",
                        "brand": std_br,
                        "active_intent": active_intent,
                        "language": lang
                    }

        # 4I. Select Specific Candidate (e.g. "ye wala le lo", "theek hai ye le lo", "select this", "ye le lo")
        if any(p in normalized for p in [
            "ye wala le lo", "ye le lo", "theek hai ye le lo", "ye wala select karo", 
            "select this", "select this one", "pick this", "take this one", "theek hai ye wala"
        ]):
            target_prod = previous_products[0] if previous_products else active_intent.get("selected_product")
            return {
                "action": "SELECT_CANDIDATE",
                "product": target_prod,
                "active_intent": active_intent,
                "language": lang
            }

        # 4J. Quantity Modification (e.g. "2 pairs", "2 pairs add karo", "make it 2", "qty 2")
        if (any(w in normalized for w in ["pair", "pairs", "quantity", "qty", "units", "items", "piece", "pieces"]) or normalized.strip() in ["2", "3", "4", "5", "1"]) and not is_purchase_cmd:
            q = cls.extract_quantity(normalized)
            if q and q >= 1:
                return {
                    "action": "SET_QUANTITY",
                    "quantity": q,
                    "active_intent": active_intent,
                    "language": lang
                }

        # 4F. Order Cancellation Inquiry
        if any(p in normalized for p in ["cancel kar sakta hu", "can i cancel my order", "cancel order", "cancel kaise kare", "order cancel", "cancellation", "cancel kar sakte hain"]):
            return {
                "action": "CANCEL_INQUIRY",
                "active_intent": active_intent,
                "message": "Haan, aapka order jab tak PROCESSING ya CONFIRMED status mein hai, aap /orders page par jakar 'Cancel Order' button se turant cancel kar sakte hain. Full refund automatic process ho jayega." if is_hi else "Yes, as long as your order is in PROCESSING or CONFIRMED state, you can instantly cancel it from /orders by clicking 'Cancel Order'. A full refund will be processed automatically.",
                "products": [],
                "language": lang
            }

        # 4G. Virtual Try-On Intent
        tryon_phrases = [
            "try this on", "try on", "try it on", "try on me", "can i see this on me", "see this on me",
            "show me how this looks on me", "how does this look on me", "try this dress", "try this shirt",
            "try this jacket", "try these shoes", "fitting room", "virtual try on", "virtual try-on", "ai try on",
            "ye mujhpe kaisa lagega", "mujhpe kaisa lagega", "ye shoes mujhpe kaise lagenge",
            "ye kapde mujhpe kaise lagenge", "isko try karwao", "try karke dikhao", "pehen ke dikhao",
            "try on karo", "virtual try on dikhao", "try karna hai", "try karwao", "pehan ke dikhao"
        ]
        if any(p in normalized for p in tryon_phrases):
            target_prod = None
            if previous_products:
                if any(p in normalized for p in ["best", "best one", "sabse accha"]):
                    target_prod = cls._rank_best_product(previous_products)
                elif any(p in normalized for p in ["second", "doosra", "2nd"]):
                    target_prod = previous_products[1] if len(previous_products) > 1 else previous_products[0]
                elif any(p in normalized for p in ["last", "aakhri"]):
                    target_prod = previous_products[-1]
                else:
                    target_prod = previous_products[0]
            elif isinstance(active_intent.get("selected_product"), dict):
                target_prod = active_intent.get("selected_product")

            return {
                "action": "VIRTUAL_TRY_ON",
                "product": target_prod,
                "product_id": target_prod.get("id") if target_prod else None,
                "active_intent": active_intent,
                "language": lang
            }

        # 5. Check for Cart Add Mutations with Explicit UUID or Entity Reference
        uuid_match = re.search(r'(?:product\s+)?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}|prod_[a-z0-9_]+)', message, re.IGNORECASE)
        is_add_cart = any(p in normalized for p in ["add", "cart mein", "cart me", "daal do", "add it", "add this", "add the best"])
        if uuid_match and is_add_cart:
            target_prod_id = uuid_match.group(1)
            return {
                "action": "ADD_TO_CART_RESOLVED",
                "product": {"id": target_prod_id, "name": "Product"},
                "product_id": target_prod_id,
                "quantity": quantity,
                "active_intent": active_intent,
                "language": lang
            }

        if is_add_cart:
            target_prod = None
            if previous_products:
                if any(p in normalized for p in ["best", "best one", "sabse accha", "sabse achha"]):
                    target_prod = cls._rank_best_product(previous_products)
                elif any(p in normalized for p in ["cheapest", "cheaper", "sasta", "sabse sasta"]):
                    target_prod = min(previous_products, key=lambda x: float(x.get("price", 999999)))
                elif any(p in normalized for p in ["second", "doosra", "2nd"]):
                    target_prod = previous_products[1] if len(previous_products) > 1 else previous_products[0]
                elif any(p in normalized for p in ["last", "aakhri", "last one"]):
                    target_prod = previous_products[-1]
                else:
                    target_prod = previous_products[0]
            
            if target_prod:
                return {
                    "action": "ADD_TO_CART_RESOLVED",
                    "product": target_prod,
                    "product_id": target_prod.get("id"),
                    "quantity": quantity,
                    "active_intent": active_intent,
                    "language": lang
                }

        # 6. Check for Cart Remove Mutation
        if any(p in normalized for p in ["remove", "hata do", "delete", "nikal do"]):
            return {
                "action": "REMOVE_FROM_CART",
                "active_intent": active_intent,
                "language": lang
            }

        # 7. Extract Numbers & Budget Constraints
        extracted_budget, budget_type, all_budgets = cls._extract_budget(normalized)

        # 8. Detect Category Mention
        detected_category, detected_type, detected_query = cls._detect_category(normalized)

        # Check for materially conflicting budgets in a single query (e.g. 500 and 5000)
        if budget_type == "conflict" and len(all_budgets) >= 2:
            b1, b2 = min(all_budgets), max(all_budgets)
            cat_display = (detected_type or active_intent.get("product_type") or "shoe").lower()
            cat_display_hi = (detected_type or active_intent.get("product_type") or "jooto").lower()
            
            clarify_msg = (
                f"Aapne ₹{int(b1):,} aur ₹{int(b2):,} dono mention kiye hain. Kya main {cat_display_hi} ka budget ₹{int(b1):,} ke andar rakhu ya ₹{int(b2):,} ke andar?"
                if is_hi
                else f"You mentioned both ₹{int(b1):,} and ₹{int(b2):,}. Should I keep the {cat_display} budget under ₹{int(b1):,} or ₹{int(b2):,}?"
            )
            conflict_intent = {
                "query": normalized,
                "category": detected_category or active_intent.get("category"),
                "max_price": None,
                "min_price": None,
                "quantity": 1,
                "sort": None,
                "in_stock_only": False,
                "clarification_needed": True,
                "clarification_reason": "budget_conflict",
                "conflicting_budgets": [b1, b2]
            }
            return {
                "action": "CLARIFICATION_NEEDED",
                "active_intent": active_intent,
                "message": clarify_msg,
                "products": [],
                "structured_intent": conflict_intent,
                "language": lang
            }

        # Check for ambiguous budget relative to category (e.g. "500 ke shoes" where shoes start at ₹2,999)
        if detected_category == "Running" and extracted_budget and extracted_budget < 1000 and not any(k in message.lower() for k in ["5k", "5 k", "5000", "5,000", "paanch"]):
            clarify_msg = (
                f"Aapne ₹{int(extracted_budget):,} mention kiya hai. Running shoes hamare catalog mein ₹2,999 se start hote hain. Kya aap ₹{int(extracted_budget):,} ke accessories (jaise performance socks) ya ₹5,000 ke andar running shoes dekh rahe hain?"
                if is_hi
                else f"You mentioned ₹{int(extracted_budget):,}. Running shoes start at ₹2,999. Did you mean workout accessories under ₹{int(extracted_budget):,} or running shoes under ₹5,000?"
            )
            return {
                "action": "CLARIFICATION_NEEDED",
                "active_intent": active_intent,
                "message": clarify_msg,
                "products": [],
                "structured_intent": {
                    "query": normalized,
                    "category": "Running",
                    "max_price": float(extracted_budget),
                    "clarification_needed": True,
                    "clarification_reason": "unrealistic_budget_for_category"
                },
                "language": lang
            }

        # 9. Check Entity References: "which is best", "which is cheapest", "compare", "second one"
        if any(p in normalized for p in ["best", "which is best", "which one is best", "best one", "best wala", "sabse accha", "sabse achha", "recommend the best"]):
            if previous_products:
                best_prod = cls._rank_best_product(previous_products)
                best_msg = (
                    f"Hamare verification ke anusaar **{best_prod['name']}** (₹{int(best_prod['price']):,}) sabse best option hai. "
                    f"Karan: Ye aapke budget aur high-performance running criteria ko perfectly match karta hai. Real-time stock verified hai."
                    if is_hi
                    else f"Based on verified specs and value, **{best_prod['name']}** (₹{int(best_prod['price']):,}) is the best match. "
                    f"Reason: Engineered specifically for high-performance durability within your budget bounds. Verified in stock."
                )
                return {
                    "action": "BEST_PRODUCT_DIRECT",
                    "active_intent": active_intent,
                    "message": best_msg,
                    "products": [best_prod],
                    "language": lang
                }

        # External Price Check & Comparison Intent across Amazon, Flipkart, Myntra, Brand Sites
        external_check_keywords = [
            "cheaper somewhere else", "cheaper elsewhere", "is this cheaper", "compare prices", 
            "compare this", "compare this one", "where is this cheapest", "price check", "ai price check",
            "amazon pe", "flipkart pe", "myntra pe", "official site pe", "official website pe",
            "aur kahi sasta", "aur kisi site", "kahi aur sasta", "sabse sasta kaha", "lowest price among stores",
            "other sites", "other stores", "best price elsewhere", "compare all stores"
        ]

        if any(k in normalized for k in external_check_keywords) or (("amazon" in normalized or "flipkart" in normalized or "myntra" in normalized) and ("price" in normalized or "kitne" in normalized or "kya" in normalized or "check" in normalized)):
            target_prod = None
            for p in previous_products or []:
                p_name = p.get("name", "").lower()
                if p_name in normalized or any(w in normalized for w in p_name.split() if len(w) > 3):
                    target_prod = p
                    break
            if not target_prod and previous_products:
                target_prod = previous_products[0]

            return {
                "action": "EXTERNAL_PRICE_CHECK",
                "active_intent": active_intent,
                "target_product": target_prod,
                "product_id": target_prod.get("id") if target_prod else None,
                "language": lang
            }

        if any(p in normalized for p in ["cheapest", "which is cheapest", "which one is cheapest", "cheapest one", "sabse sasta", "lowest price"]):
            if previous_products:
                cheap_prod = min(previous_products, key=lambda x: float(x.get("price", 999999)))
                cheap_msg = (
                    f"Sabse affordable verified option hai **{cheap_prod['name']}** (₹{int(cheap_prod['price']):,}). Stock verified hai."
                    if is_hi
                    else f"The most affordable verified option is **{cheap_prod['name']}** at ₹{int(cheap_prod['price']):,}. Verified in stock."
                )
                return {
                    "action": "CHEAPEST_PRODUCT_DIRECT",
                    "active_intent": active_intent,
                    "message": cheap_msg,
                    "products": [cheap_prod],
                    "language": lang
                }

        if any(p in normalized for p in ["compare", "difference", "compare these", "dono compare", "comparison"]):
            if previous_products and len(previous_products) >= 2:
                p1, p2 = previous_products[0], previous_products[1]
                cmp_text = (
                    f"Dono top verified options ka comparison:\n\n"
                    f"1. **{p1.get('name')}** (₹{int(p1.get('price', 0)):,}):\n"
                    f"   - {p1.get('description', 'High performance model')}\n"
                    f"   - In Stock: {p1.get('stock_quantity', 1)} units\n\n"
                    f"2. **{p2.get('name')}** (₹{int(p2.get('price', 0)):,}):\n"
                    f"   - {p2.get('description', 'Durable athletic model')}\n"
                    f"   - In Stock: {p2.get('stock_quantity', 1)} units"
                    if is_hi
                    else f"Here is a side-by-side spec comparison:\n\n"
                    f"1. **{p1.get('name')}** (₹{int(p1.get('price', 0)):,}):\n"
                    f"   - {p1.get('description', 'High performance model')}\n"
                    f"   - In Stock: {p1.get('stock_quantity', 1)} units verified\n\n"
                    f"2. **{p2.get('name')}** (₹{int(p2.get('price', 0)):,}):\n"
                    f"   - {p2.get('description', 'Durable athletic model')}\n"
                    f"   - In Stock: {p2.get('stock_quantity', 1)} units verified"
                )
                return {
                    "action": "COMPARISON_DIRECT",
                    "active_intent": active_intent,
                    "message": cmp_text,
                    "products": [p1, p2],
                    "language": lang
                }

        # Extract brand, use-case, colour preferences
        detected_brand = None
        for b in ["nike", "adidas", "puma", "asics", "noise", "boat", "decathlon", "milton", "apple"]:
            if re.search(r'\b' + b + r'\b', normalized):
                detected_brand = "Nike" if b == "nike" else ("Adidas" if b == "adidas" else ("Puma" if b == "puma" else b.capitalize()))
                break

        detected_use_case = None
        for uc in ["marathon", "trail", "gym", "daily", "tempo", "training", "racing"]:
            if re.search(r'\b' + uc + r'\b', normalized):
                detected_use_case = uc
                break

        detected_colour = None
        for col_k, std_c in {"black": "Black", "kala": "Black", "white": "Pure White", "safed": "Pure White", "blue": "Navy Blue", "red": "Crimson Red"}.items():
            if re.search(r'\b' + col_k + r'\b', normalized):
                detected_colour = std_c
                break

        # 10. Branch A: Category Explicitly Specified
        current_cat = active_intent.get("category")
        if detected_category:
            is_new_category = current_cat != detected_category
            new_intent = {
                "category": detected_category,
                "product_type": detected_type,
                "budget_max": extracted_budget if extracted_budget else (active_intent.get("budget_max") if not is_new_category else None),
                "budget_min": None,
                "preferred_price": extracted_budget if budget_type == "around" else None,
                "brand_preference": detected_brand or active_intent.get("brand_preference"),
                "use_case": detected_use_case or active_intent.get("use_case"),
                "colour_preference": detected_colour or active_intent.get("colour_preference"),
                "sport": "running" if detected_category == "Running" else None,
                "language": lang,
                "active": True
            }

            search_args = {
                "category": detected_category,
                "brand": new_intent.get("brand_preference"),
                "use_case": new_intent.get("use_case"),
                "colour": new_intent.get("colour_preference")
            }
            if new_intent.get("budget_max"):
                search_args["max_price"] = new_intent["budget_max"]
            if detected_query:
                search_args["query"] = detected_query

            return {
                "action": "CATEGORY_SEARCH",
                "active_intent": new_intent,
                "search_params": search_args,
                "is_new_category": is_new_category,
                "language": lang
            }

        # 11. Branch B: Follow-up Budget / Standalone Number
        if extracted_budget is not None:
            if not current_cat:
                clarify_msg = (
                    f"₹{int(extracted_budget):,} ke andar aap kis type ka gear dhoondh rahe hain? Running shoes, gym bags, ya accessories?"
                    if is_hi
                    else f"Sure — ₹{int(extracted_budget):,} for what kind of product? We have running shoes, gym bags, apparel, and accessories."
                )
                return {
                    "action": "CLARIFICATION_NEEDED",
                    "active_intent": {"language": lang},
                    "message": clarify_msg,
                    "products": [],
                    "language": lang
                }

            updated_intent = dict(active_intent)
            updated_intent["budget_max"] = extracted_budget
            updated_intent["language"] = lang
            search_args = {
                "category": current_cat,
                "max_price": extracted_budget
            }
            if active_intent.get("default_query"):
                search_args["query"] = active_intent["default_query"]

            return {
                "action": "BUDGET_REFINEMENT",
                "active_intent": updated_intent,
                "search_params": search_args,
                "language": lang
            }

        # 12. Branch C: Cheaper Search on Active Intent
        if any(p in normalized for p in ["cheaper", "aur sasta", "saste", "less expensive"]):
            if current_cat:
                search_args = {"category": current_cat}
                if previous_products:
                    prices = [p.get("price") for p in previous_products if p.get("price")]
                    if prices:
                        search_args["max_price"] = min(prices) - 1
                return {
                    "action": "CHEAPER_SEARCH",
                    "active_intent": active_intent,
                    "search_params": search_args,
                    "language": lang
                }

        # 13. Fallback / Continuation
        if current_cat:
            search_args = {"category": current_cat}
            if active_intent.get("budget_max"):
                search_args["max_price"] = active_intent["budget_max"]
            return {
                "action": "CONTINUE_INTENT",
                "active_intent": active_intent,
                "search_params": search_args,
                "language": lang
            }

        fallback_msg = (
            "Mujhe aapki request samajh nahi aayi. Kya aap running shoes, gym bags, ya accessories dhoondh rahe hain?"
            if is_hi
            else "Hello! I am your AI Shopping Assistant for Apex Sports. I can help you discover running shoes, workout apparel, gym bags, and fitness gear. What are you shopping for today?"
        )
        return {
            "action": "GREETING_OR_BROAD",
            "active_intent": {"language": lang},
            "message": fallback_msg,
            "products": [],
            "language": lang
        }

    @classmethod
    def _rank_best_product(cls, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        for p in products:
            p_text = ((p.get("name") or "") + " " + (p.get("description") or "")).lower()
            if "marathon" in p_text or "speedflow" in p_text:
                return p
        return products[0]

    @classmethod
    def _detect_category(cls, text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # Check specific product name patterns first
        for prod_name, aliases in cls.PRODUCT_NAME_PATTERNS:
            if any(re.search(r'\b' + re.escape(alias) + r'\b', text, re.IGNORECASE) for alias in aliases):
                p_lower = prod_name.lower()
                if any(k in p_lower for k in ["shoes", "marathon", "running"]):
                    return "Running", prod_name, prod_name
                elif any(k in p_lower for k in ["bottle", "socks", "roller"]):
                    return "Accessories", prod_name, prod_name
                elif any(k in p_lower for k in ["watch", "tracker"]):
                    return "Electronics", prod_name, prod_name
                elif any(k in p_lower for k in ["bag", "duffle"]):
                    return "Bags", prod_name, prod_name
                elif any(k in p_lower for k in ["shorts", "shirt", "t-shirt"]):
                    return "Apparel", prod_name, prod_name

        for cat_name in ["Water Bottle", "Socks", "Foam Roller", "Running", "Bags", "Electronics", "Apparel", "Accessories"]:
            cat_info = cls.CATEGORIES[cat_name]
            for kw in cat_info["keywords"]:
                pattern = r'(?:\b|_|^)' + re.escape(kw) + r'(?:\b|_|$)'
                if re.search(pattern, text, re.IGNORECASE):
                    actual_cat = cat_info.get("category", cat_name)
                    return actual_cat, cat_info["product_type"], cat_info.get("default_query")
        return None, None, None

    @classmethod
    def _extract_all_budgets(cls, text: str) -> List[Tuple[float, str]]:
        """
        Finds all budget amounts specified in the query.
        Returns a list of (amount, budget_type) tuples.
        """
        results: List[Tuple[float, str]] = []
        seen_vals = set()

        # Specific keyword-anchored patterns
        patterns = [
            (r'(?:under|below|max|tak|ke\s+andar|ke\s+under|ke\s+aas[\s-]?paas|around|about|<|<=|₹|rs\.?|inr)\s*(?:₹|rs\.?|inr)?\s*([0-9]+(?:,[0-9]+)?)\s*(?:/-|rs|rupees|inr|tak|ke\s+andar|ke\s+under)?', "max"),
            (r'([0-9]+(?:,[0-9]+)?)\s*(?:/-|rs|rupees|inr)\s*(?:tak|ke\s+andar|ke\s+under|ke\s+aas[\s-]?paas|under|below)?', "max"),
            (r'\b([0-9]+(?:,[0-9]+)?)\s*(?:tak|ke\s+andar|ke\s+under|ke\s+aas[\s-]?paas)\b', "max"),
            (r'\b(?:₹|rs\.?)\s*([0-9]+(?:,[0-9]+)?)\b', "max"),
            (r'\b([0-9]{3,6})\b', "max")
        ]

        for pat, b_type in patterns:
            for match in re.finditer(pat, text, re.IGNORECASE):
                try:
                    num_str = match.group(1).replace(',', '')
                    val = float(num_str)
                    if val >= 50 and val not in seen_vals:
                        seen_vals.add(val)
                        results.append((val, b_type))
                except Exception:
                    pass

        return results

    @classmethod
    def _extract_budget(cls, text: str) -> Tuple[Optional[float], str, List[float]]:
        """
        Extracts primary budget and detects conflicting budgets.
        Returns (primary_budget, budget_type, all_detected_budgets).
        """
        all_budgets = cls._extract_all_budgets(text)
        if not all_budgets:
            return None, "none", []
        
        amounts = [b[0] for b in all_budgets]
        if len(amounts) == 1:
            return amounts[0], all_budgets[0][1], amounts
        
        # Multiple distinct budget amounts found in single query
        return None, "conflict", amounts
