from decimal import Decimal
from typing import List, Dict, Any

# Existing baseline products (10 items) with genuine verified identity
BASELINE_PRODUCTS: List[Dict[str, Any]] = [
    {
        "name": "Pro Running Shoes",
        "description": "High performance lightweight breathable running shoes with reactive cushioning and high-durability carbon rubber outsole.",
        "brand": "Nike",
        "category": "Running",
        "subcategory": "Running Shoes",
        "price": Decimal("3499.00"),
        "mrp": Decimal("4499.00"),
        "currency": "INR",
        "stock": 50,
        "gtin": "0195244584285",
        "model_number": "DC3728-003",
        "sku": "NK-DC3728-003",
        "rating": 4.6,
        "review_count": 142,
        "tags": ["running", "shoes", "nike", "marathon", "breathable", "cushioned", "black"],
        "attributes": {"color": "Black", "style": "DC3728-003", "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop&q=80"},
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop&q=80",
        "external_offers": [
            {"store_domain": "amazon.in", "price": None, "mrp": None, "external_url": "https://www.amazon.in/s?k=Nike+Revolution+6+DC3728-003", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Retailer search query fallback"},
            {"store_domain": "flipkart.com", "price": None, "mrp": None, "external_url": "https://www.flipkart.com/search?q=Nike+Revolution+6+DC3728", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Retailer search query fallback"},
            {"store_domain": "myntra.com", "price": None, "mrp": None, "external_url": "https://www.myntra.com/nike-running-shoes", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Retailer search query fallback"},
            {
                "store_domain": "nike.com",
                "price": Decimal("3695.00"),
                "mrp": Decimal("3695.00"),
                "external_title": "Nike Revolution 6 Men's Road Running Shoes",
                "external_url": "https://www.nike.com/in/t/revolution-6-road-running-shoes-NCvPsq/DC3728-003",
                "image_url": "https://static.nike.com/a/images/t_PDP_1280_v1/f_auto,q_auto:eco/e777ecda-a948-4444-be1f-1eb728b9d81d/revolution-6-road-running-shoes-NCvPsq.png",
                "match_type": "EXACT_PRODUCT",
                "confidence": 1.0,
                "reason": "Official Manufacturer D2C Style Index",
                "identity_evidence": {
                    "type": "OFFICIAL_MANUFACTURER_SKU",
                    "style_code": "DC3728-003",
                    "gtin": "0195244584285",
                    "source": "Nike Direct D2C Style Index",
                    "pdp_verified": True,
                    "image_verified": True
                }
            }
        ]
    },
    {
        "name": "SpeedFlow Marathon Shoes",
        "description": "Ultra-lightweight aerodynamic road racing shoes engineered for marathon tempo pacing and energy return.",
        "brand": "Adidas",
        "category": "Running",
        "subcategory": "Running Shoes",
        "price": Decimal("2999.00"),
        "mrp": Decimal("3999.00"),
        "currency": "INR",
        "stock": 40,
        "gtin": "4066749964179",
        "model_number": "IE7263",
        "sku": "AD-IE7263-UK8",
        "rating": 4.8,
        "review_count": 210,
        "tags": ["marathon", "adidas", "shoes", "tempo", "lightweight", "black"],
        "attributes": {"color": "Core Black", "style": "IE7263", "image_url": "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=600&auto=format&fit=crop&q=80"},
        "image_url": "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=600&auto=format&fit=crop&q=80",
        "external_offers": [
            {"store_domain": "amazon.in", "price": None, "mrp": None, "external_url": "https://www.amazon.in/s?k=Adidas+Duramo+Speed+IE7263", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Retailer search query fallback"},
            {"store_domain": "flipkart.com", "price": None, "mrp": None, "external_url": "https://www.flipkart.com/search?q=SpeedFlow+Marathon+Shoes", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Retailer search query fallback"},
            {
                "store_domain": "adidas.co.in",
                "price": Decimal("4599.00"),
                "mrp": Decimal("6599.00"),
                "external_title": "Adidas Duramo Speed Shoes - Black",
                "external_url": "https://www.adidas.co.in/duramo-speed-shoes/IE7263.html",
                "image_url": "https://assets.adidas.com/images/h_840,f_auto,q_auto,fl_lossy,c_fill,g_auto/71a62d04ca03496c8135af8600f72ec6_9366/Duramo_Speed_Shoes_Black_IE7263_01_standard.jpg",
                "match_type": "EXACT_PRODUCT",
                "confidence": 1.0,
                "reason": "Official Adidas Store",
                "identity_evidence": {
                    "type": "OFFICIAL_MANUFACTURER_SKU",
                    "style_code": "IE7263",
                    "gtin": "4066749964179",
                    "source": "Adidas Official Direct Catalog",
                    "pdp_verified": True,
                    "image_verified": True
                }
            }
        ]
    },
    {
        "name": "Air Cushion Trail Running Shoes",
        "description": "Rugged all-terrain trail running shoes with vibram grip and carbon stability plate.",
        "brand": "Apex Sports",
        "category": "Running",
        "subcategory": "Running Shoes",
        "price": Decimal("4299.00"),
        "mrp": Decimal("5499.00"),
        "currency": "INR",
        "stock": 35,
        "gtin": None,
        "model_number": None,
        "sku": "APX-AIR-TRL-03",
        "rating": 4.5,
        "review_count": 89,
        "tags": ["trail", "running", "shoes", "all-terrain", "apex"],
        "image_url": "https://images.unsplash.com/photo-1608231387042-66d1773070a5?w=600&auto=format&fit=crop&q=80",
        "external_offers": []
    },
    {
        "name": "Performance Socks",
        "description": "Moisture-wicking anti-blister athletic running socks with arch support.",
        "brand": "Apex Sports",
        "category": "Accessories",
        "subcategory": "Socks",
        "price": Decimal("399.00"),
        "mrp": Decimal("499.00"),
        "currency": "INR",
        "stock": 200,
        "gtin": None,
        "model_number": None,
        "sku": "APX-SCK-01",
        "rating": 4.4,
        "review_count": 95,
        "tags": ["socks", "accessories", "athletic", "apex"],
        "image_url": "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?w=600&auto=format&fit=crop&q=80",
        "external_offers": []
    },
    {
        "name": "Fitness Tracker Watch",
        "description": "Smart sports watch with integrated GPS, heart rate monitor, and 14-day battery life.",
        "brand": "Noise",
        "category": "Electronics",
        "subcategory": "Smart Watches",
        "price": Decimal("8500.00"),
        "mrp": Decimal("9999.00"),
        "currency": "INR",
        "stock": 30,
        "gtin": None,
        "model_number": None,
        "sku": "NS-WTCH-01",
        "rating": 4.7,
        "review_count": 340,
        "tags": ["watch", "smartwatch", "fitness", "gps", "electronics"],
        "image_url": "https://images.unsplash.com/photo-1575311373937-040b8e1fd5b6?w=600&auto=format&fit=crop&q=80",
        "external_offers": [
            {"store_domain": "amazon.in", "price": None, "mrp": None, "external_url": "https://www.amazon.in/s?k=Noise+ColorFit+Smartwatch", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Retailer search query fallback"},
            {"store_domain": "flipkart.com", "price": None, "mrp": None, "external_url": "https://www.flipkart.com/search?q=Noise+Smartwatch", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Retailer search query fallback"}
        ]
    },
    {
        "name": "Gym Duffle Bag",
        "description": "Water-resistant 40L training duffle with separate ventilated shoe compartment.",
        "brand": "Apex Sports",
        "category": "Bags",
        "subcategory": "Gym Bags",
        "price": Decimal("1899.00"),
        "mrp": Decimal("2499.00"),
        "currency": "INR",
        "stock": 45,
        "gtin": None,
        "model_number": None,
        "sku": "APX-BAG-01",
        "rating": 4.5,
        "review_count": 67,
        "tags": ["bag", "gym", "duffle", "accessories", "apex"],
        "image_url": "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600&auto=format&fit=crop&q=80",
        "external_offers": []
    },
    {
        "name": "Sports Dry-Fit T-Shirt",
        "description": "Ultra-breathable athletic gym training shirt with 4-way stretch fabric and moisture-wicking Dri-FIT technology.",
        "brand": "Nike",
        "category": "Apparel",
        "subcategory": "T-Shirts",
        "price": Decimal("999.00"),
        "mrp": Decimal("1499.00"),
        "currency": "INR",
        "stock": 80,
        "gtin": None,
        "model_number": "718833-010",
        "sku": "NK-718833-010-M",
        "rating": 4.6,
        "review_count": 112,
        "tags": ["shirt", "t-shirt", "dry-fit", "apparel", "nike", "training"],
        "image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600&auto=format&fit=crop&q=80",
        "attributes": {
            "vto_image_ready": True,
            "color": "Classic Black",
            "size": "Medium",
            "model": "Dri-FIT Legend Short-Sleeve",
            "style_code": "718833-010",
            "variant_images": {
                "Classic Black": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600&auto=format&fit=crop&q=80",
                "Pure White": "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=600&auto=format&fit=crop&q=80",
                "Navy Blue": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=600&auto=format&fit=crop&q=80",
                "Crimson Red": "https://images.unsplash.com/photo-1618354691438-25bc04584c23?w=600&auto=format&fit=crop&q=80"
            },
            "variant_details": {
                "Classic Black": {
                    "color": "Classic Black",
                    "style_code": "718833-010",
                    "gtin": None,
                    "garment_image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600&auto=format&fit=crop&q=80",
                    "vto_eligible": True
                },
                "Pure White": {
                    "color": "Pure White",
                    "style_code": "718833-100",
                    "gtin": None,
                    "garment_image_url": "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=600&auto=format&fit=crop&q=80",
                    "vto_eligible": True
                },
                "Navy Blue": {
                    "color": "Navy Blue",
                    "style_code": "718833-451",
                    "gtin": None,
                    "garment_image_url": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=600&auto=format&fit=crop&q=80",
                    "vto_eligible": True
                },
                "Crimson Red": {
                    "color": "Crimson Red",
                    "style_code": "718833-657",
                    "gtin": None,
                    "garment_image_url": "https://images.unsplash.com/photo-1618354691438-25bc04584c23?w=600&auto=format&fit=crop&q=80",
                    "vto_eligible": True
                }
            }
        },
        "external_offers": [
            {"store_domain": "amazon.in", "price": None, "mrp": None, "external_title": "Search Nike Dri-FIT Legend on Amazon India", "external_url": "https://www.amazon.in/s?k=Nike+Dri-FIT+Legend+718833-010", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Direct active Amazon India listing unverified"},
            {"store_domain": "myntra.com", "price": None, "mrp": None, "external_title": "Search Nike Dri-FIT T-Shirts on Myntra", "external_url": "https://www.myntra.com/nike-dri-fit-tshirt", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Myntra catalog active style listing unverified"},
            {
                "store_domain": "nike.com",
                "price": Decimal("1095.00"),
                "mrp": Decimal("1095.00"),
                "external_title": "Nike Dri-FIT Legend Men's Training T-Shirt",
                "external_url": "https://www.nike.com/in/t/dri-fit-legend-training-t-shirt-1ZtbXq/718833-010",
                "image_url": "https://static.nike.com/a/images/t_PDP_1280_v1/f_auto,q_auto:eco/718833-010/dri-fit-legend-mens-training-t-shirt.png",
                "match_type": "EXACT_PRODUCT",
                "confidence": 1.0,
                "reason": "Official Manufacturer D2C Style Index",
                "identity_evidence": {
                    "type": "OFFICIAL_MANUFACTURER_SKU",
                    "style_code": "718833-010",
                    "gtin": None,
                    "source": "Nike Direct D2C Style Index",
                    "pdp_verified": True,
                    "image_verified": True
                }
            }
        ]
    },
    {
        "name": "Running Shorts",
        "description": "Lightweight athletic gym training shorts with moisture-wicking interlock fabric.",
        "brand": "Puma",
        "category": "Apparel",
        "subcategory": "Shorts",
        "price": Decimal("1299.00"),
        "mrp": Decimal("1799.00"),
        "currency": "INR",
        "stock": 60,
        "gtin": "4063697428416",
        "model_number": "58672801",
        "sku": "PM-58672801-M",
        "rating": 4.5,
        "review_count": 78,
        "tags": ["shorts", "running", "puma", "apparel"],
        "image_url": "https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=600&auto=format&fit=crop&q=80",
        "attributes": {
            "vto_image_ready": True,
            "color": "Puma Black",
            "size": "Medium",
            "model": "Active Interlock Shorts",
            "style_code": "58672801",
            "variant_images": {
                "Puma Black": "https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=600&auto=format&fit=crop&q=80"
            },
            "variant_details": {
                "Puma Black": {
                    "color": "Puma Black",
                    "style_code": "58672801",
                    "gtin": "4063697428416",
                    "garment_image_url": "https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=600&auto=format&fit=crop&q=80",
                    "vto_eligible": True
                }
            }
        },
        "external_offers": [
            {"store_domain": "amazon.in", "price": None, "mrp": None, "external_url": "https://www.amazon.in/s?k=Puma+Active+Interlock+Shorts+586728", "match_type": "SEARCH_FALLBACK", "confidence": 0.60, "reason": "Retailer search query fallback"},
            {
                "store_domain": "puma.com",
                "price": Decimal("1199.00"),
                "mrp": Decimal("1499.00"),
                "external_title": "Puma Active Men's Interlock Shorts",
                "external_url": "https://in.puma.com/in/en/pd/active-mens-interlock-shorts/586728",
                "image_url": "https://images.puma.com/image/upload/f_auto,q_auto,b_rgb:fafafa,w_750,h_750/global/586728/01/fnd/IND/fmt/png/Active-Men's-Interlock-Shorts",
                "match_type": "EXACT_PRODUCT",
                "confidence": 1.0,
                "reason": "Official Puma Direct D2C Index",
                "identity_evidence": {
                    "type": "OFFICIAL_MANUFACTURER_SKU",
                    "style_code": "58672801",
                    "gtin": "4063697428416",
                    "source": "Puma Direct D2C Style Index",
                    "pdp_verified": True,
                    "image_verified": True
                }
            }
        ]
    },
    {
        "name": "Insulated Stainless Steel Water Bottle",
        "description": "Vacuum insulated 750ml leakproof sports flask keeping drinks cold for 24 hours.",
        "brand": "Apex Sports",
        "category": "Accessories",
        "subcategory": "Water Bottles",
        "price": Decimal("699.00"),
        "mrp": Decimal("999.00"),
        "currency": "INR",
        "stock": 120,
        "gtin": None,
        "model_number": None,
        "sku": "APX-BOT-750",
        "rating": 4.7,
        "review_count": 310,
        "tags": ["bottle", "water bottle", "flask", "accessories", "apex"],
        "image_url": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&auto=format&fit=crop&q=80",
        "external_offers": []
    },
    {
        "name": "Deep Tissue Foam Recovery Roller",
        "description": "High-density EVA muscle foam roller for post-workout mobility and soreness relief.",
        "brand": "Apex Sports",
        "category": "Accessories",
        "subcategory": "Foam Rollers",
        "price": Decimal("799.00"),
        "mrp": Decimal("1199.00"),
        "currency": "INR",
        "stock": 90,
        "gtin": None,
        "model_number": None,
        "sku": "APX-ROL-01",
        "rating": 4.6,
        "review_count": 140,
        "tags": ["roller", "foam roller", "accessories", "fitness", "recovery", "apex"],
        "image_url": "https://images.unsplash.com/photo-1600881333168-2ef49b341f30?w=600&auto=format&fit=crop&q=80",
        "external_offers": []
    }
]

def generate_marketplace_products() -> List[Dict[str, Any]]:
    all_products = list(BASELINE_PRODUCTS)

    category_data = [
        # 1. Sports & Fitness
        ("Sports & Fitness", "Running Shoes", "Nike", "Nike Air Zoom Pegasus 40", "Premium daily trainer with responsive Zoom Air cushioning and engineered mesh upper.", Decimal("4799.00"), Decimal("5999.00"), 4.7, 340, "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Running Shoes", "Adidas", "Adidas Ultraboost Light 23", "Iconic energy-returning Boost midsole running shoe for long distance endurance.", Decimal("5499.00"), Decimal("6999.00"), 4.8, 412, "https://images.unsplash.com/photo-1587563871167-1ee9c731aefb?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Training Shoes", "Puma", "Puma Fuse 2.0 Cross Training Shoes", "Engineered stability shoe for heavy deadlifts and functional high-intensity workouts.", Decimal("3299.00"), Decimal("4299.00"), 4.5, 120, "https://images.unsplash.com/photo-1575537302964-96cd47c06b1b?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Football Shoes", "Nike", "Nike Mercurial Vapor 15 Club", "Moulded synthetic upper speed cleats with turf studs for explosive acceleration.", Decimal("3899.00"), Decimal("4999.00"), 4.6, 95, "https://images.unsplash.com/photo-1511556532299-8f662fc26c06?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Basketball Shoes", "Nike", "Nike Precision 6 Low Basketball", "Quick-cut grip traction and sculpted foam midsole for ultimate court control.", Decimal("4499.00"), Decimal("5499.00"), 4.4, 76, "https://images.unsplash.com/photo-1579338559194-a162d19bf842?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Cricket Shoes", "Asics", "Asics Gel-Peake Cricket Spikes", "Reinforced toe protection and GEL shock absorption for turf wickets and pitch traction.", Decimal("4999.00"), Decimal("6499.00"), 4.6, 64, "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Gym Gloves", "Decathlon", "Domyos Weightlifting Grip Gloves", "Anti-callus breathable palm padding with wrist wrap support for heavy lifting.", Decimal("499.00"), Decimal("699.00"), 4.3, 180, "https://images.unsplash.com/photo-1583473848882-f9a5bc7fd2ee?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Yoga Mats", "Decathlon", "Kimjaly 8mm High-Grip Yoga Mat", "Non-slip eco-friendly textured TPE yoga and pilates exercise mat with alignment marks.", Decimal("999.00"), Decimal("1499.00"), 4.7, 230, "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Resistance Bands", "Decathlon", "Core Strength Resistance Band Set (5-Pack)", "Natural latex loop exercise bands from 5kg to 30kg resistance for mobility and activation.", Decimal("699.00"), Decimal("999.00"), 4.5, 310, "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Dumbbells", "Decathlon", "Cast Iron Hex Dumbbell Pair 5kg", "Anti-roll rubber-coated hex dumbbells for home gym and strength conditioning.", Decimal("1799.00"), Decimal("2299.00"), 4.8, 140, "https://images.unsplash.com/photo-1586401100295-7a8096fd231a?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Kettlebells", "Decathlon", "Competition Cast Iron Kettlebell 12kg", "Ergonomic wide grip handle for kettlebell swings, snatches, and goblet squats.", Decimal("2199.00"), Decimal("2799.00"), 4.7, 85, "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Skipping Ropes", "Nike", "Nike Speed Skipping Jump Rope", "Smooth bearing fast cable jump rope with adjustable steel wire for cardio conditioning.", Decimal("799.00"), Decimal("1199.00"), 4.4, 190, "https://images.unsplash.com/photo-1598289431512-b97b0917affc?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Shakers", "Puma", "Puma Pro Protein Shaker Bottle 700ml", "BPA-free leakproof shaker with stainless steel blending whisk ball and measurement markings.", Decimal("349.00"), Decimal("499.00"), 4.5, 270, "https://images.unsplash.com/photo-1577937927133-66ef06acdf18?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Sports Bras", "Nike", "Nike Dri-FIT Swoosh Medium Support Bra", "Compressive fit sports bra for running and high-intensity gym sessions.", Decimal("1499.00"), Decimal("2195.00"), 4.6, 92, "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=600&auto=format&fit=crop&q=80", True),
        ("Sports & Fitness", "Track Pants", "Adidas", "Adidas Tiro 23 Training Track Pants", "Moisture-absorbing tapered pants with ankle zips for football and athletic training.", Decimal("1899.00"), Decimal("2499.00"), 4.7, 185, "https://images.unsplash.com/photo-1552902865-b72c031ac5ea?w=600&auto=format&fit=crop&q=80", True),

        # 2. Electronics
        ("Electronics", "Earbuds", "Boat", "boAt Airdopes 141 ANC Earbuds", "42-hour playtime, 32dB Active Noise Cancellation, and BEAST gaming mode.", Decimal("1299.00"), Decimal("2490.00"), 4.4, 820, "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Earbuds", "Sony", "Sony WF-1000XM5 Premium Noise Cancelling Earbuds", "Industry leading noise cancellation with High-Resolution LDAC audio.", Decimal("19990.00"), Decimal("24990.00"), 4.8, 310, "https://images.unsplash.com/photo-1606220588913-b3aacb4d2f46?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Headphones", "Sony", "Sony WH-CH520 Wireless Bluetooth Headphones", "50 hours battery life with DSEE audio upscaling and multipoint pairing.", Decimal("3990.00"), Decimal("4990.00"), 4.6, 540, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Headphones", "Boat", "boAt Rockerz 450 Bluetooth On-Ear Headphones", "15 hours playback, 40mm dynamic drivers, and ultra-soft ear cushions.", Decimal("1199.00"), Decimal("2990.00"), 4.3, 1200, "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Smart Watches", "Apple", "Apple Watch SE (2nd Gen) GPS 44mm", "Retina display, Crash Detection, Workout app, and heart health metrics.", Decimal("26900.00"), Decimal("29900.00"), 4.9, 480, "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Smart Watches", "Noise", "Noise ColorFit Pulse 3 Smartwatch", "1.96-inch TFT display with BT Calling and 100+ sports modes.", Decimal("1499.00"), Decimal("4999.00"), 4.3, 760, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Bluetooth Speakers", "Boat", "boAt Stone 352 10W Portable Speaker", "IPX7 water resistant, 12 hours playtime, and true wireless stereo.", Decimal("1499.00"), Decimal("3490.00"), 4.5, 410, "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Power Banks", "Mi", "Xiaomi 20000mAh 33W Fast Charging Power Bank", "Triple port output with Type-C two-way fast charging power delivery.", Decimal("1999.00"), Decimal("2999.00"), 4.7, 650, "https://images.unsplash.com/photo-1609592424361-b4f7a26f04c6?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Keyboards", "Logitech", "Logitech K380 Multi-Device Wireless Keyboard", "Compact Bluetooth keyboard compatible with Windows, Mac, iPad and Android.", Decimal("2495.00"), Decimal("3195.00"), 4.8, 380, "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Mice", "Logitech", "Logitech Pebble M350 Silent Wireless Mouse", "Slim portable silent click optical mouse with dual Bluetooth/USB dongle.", Decimal("1395.00"), Decimal("1995.00"), 4.7, 520, "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&auto=format&fit=crop&q=80", True),
        ("Electronics", "Monitors", "Samsung", "Samsung 24-Inch IPS FHD Borderless Monitor", "75Hz refresh rate with AMD FreeSync and eye saver flicker-free mode.", Decimal("7499.00"), Decimal("11200.00"), 4.6, 210, "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=600&auto=format&fit=crop&q=80", True),

        # 3. Fashion
        ("Fashion", "Sneakers", "Puma", "Puma Smashic Casual Classic Sneakers", "Sleek low-boot leather tennis shoe with cushioned SoftFoam+ sockliner.", Decimal("2199.00"), Decimal("3999.00"), 4.5, 340, "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=600&auto=format&fit=crop&q=80", True),
        ("Fashion", "Sneakers", "Nike", "Nike Court Vision Low Casual Shoes", "Retro 80s basketball-inspired leather low-top lifestyle sneakers.", Decimal("3799.00"), Decimal("4995.00"), 4.6, 290, "https://images.unsplash.com/photo-1597045566677-8cf032ed6634?w=600&auto=format&fit=crop&q=80", True),
        ("Fashion", "T-Shirts", "Levi's", "Levi's Men Cotton Graphic Logo Tee", "100% pure combed jersey cotton relaxed crewneck everyday t-shirt.", Decimal("799.00"), Decimal("1299.00"), 4.4, 430, "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=600&auto=format&fit=crop&q=80", True),
        ("Fashion", "Jeans", "Levi's", "Levi's 511 Slim Fit Stretch Denim Jeans", "Classic modern slim cut jeans with responsive comfort stretch fabric.", Decimal("2199.00"), Decimal("3299.00"), 4.7, 510, "https://images.unsplash.com/photo-1542272604-780c96856592?w=600&auto=format&fit=crop&q=80", True),
        ("Fashion", "Jackets", "Puma", "Puma Windbreaker Hooded Running Jacket", "Water-repellent ultralight wind protection jacket with zip pockets.", Decimal("2499.00"), Decimal("3999.00"), 4.5, 110, "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&auto=format&fit=crop&q=80", True),
        ("Fashion", "Sunglasses", "Ray-Ban", "Ray-Ban Aviator Classic Polarized Sunglasses", "Crystal green polarized G-15 lenses with gold metal wireframes.", Decimal("6890.00"), Decimal("8590.00"), 4.8, 190, "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=600&auto=format&fit=crop&q=80", True),
        ("Fashion", "Watches", "Fossil", "Fossil Grant Chronograph Leather Watch", "Roman numeral blue dial with genuine brown leather strap and stopwatch.", Decimal("7195.00"), Decimal("11995.00"), 4.7, 240, "https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=600&auto=format&fit=crop&q=80", True),

        # 4. Home & Kitchen
        ("Home & Kitchen", "Cookware", "Prestige", "Prestige Omega Deluxe Induction Fry Pan 24cm", "Non-stick granite coating with cool-touch ergonomic bakelite handle.", Decimal("999.00"), Decimal("1450.00"), 4.5, 410, "https://images.unsplash.com/photo-1584990347449-3974488340d2?w=600&auto=format&fit=crop&q=80", True),
        ("Home & Kitchen", "Kitchen Appliances", "Philips", "Philips Daily Collection 750W Juicer Mixer Grinder", "3 stainless steel heavy duty jars with PowerChop technology.", Decimal("2999.00"), Decimal("4295.00"), 4.6, 680, "https://images.unsplash.com/photo-1570222094114-d054a817e56b?w=600&auto=format&fit=crop&q=80", True),
        ("Home & Kitchen", "Coffee Mugs", "Milton", "Milton ThermoSteel Insulated Coffee Travel Tumbler", "Double wall stainless steel 400ml leakproof flip lid hot coffee mug.", Decimal("499.00"), Decimal("750.00"), 4.7, 320, "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=600&auto=format&fit=crop&q=80", True),
        ("Home & Kitchen", "Storage", "Milton", "Milton MicroWow Insulated Casserole Set (3-Piece)", "Thermal insulated food hot-pot containers preserving temperature for 6 hours.", Decimal("1199.00"), Decimal("1650.00"), 4.6, 210, "https://images.unsplash.com/photo-1590736969955-71cc94801759?w=600&auto=format&fit=crop&q=80", True),

        # 5. Beauty & Personal Care
        ("Beauty & Personal Care", "Grooming", "Philips", "Philips OneBlade Hybrid Beard Trimmer & Shaver", "Dual-sided blade with 3 stubble combs for trimming, edging and shaving.", Decimal("1499.00"), Decimal("2195.00"), 4.6, 890, "https://images.unsplash.com/photo-1621607512214-68297480165e?w=600&auto=format&fit=crop&q=80", True),
        ("Beauty & Personal Care", "Skincare", "Nivea", "Nivea Men Dark Spot Reduction Moisturizer 50ml", "SPF30 UV protection non-sticky fast absorbing whitening face cream.", Decimal("249.00"), Decimal("350.00"), 4.4, 610, "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=600&auto=format&fit=crop&q=80", True),
        ("Beauty & Personal Care", "Haircare", "Philips", "Philips Essential Care 1200W Compact Hair Dryer", "ThermoProtect temperature setting with foldable compact travel handle.", Decimal("899.00"), Decimal("1295.00"), 4.5, 450, "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=600&auto=format&fit=crop&q=80", True),

        # 6. Travel
        ("Travel", "Luggage", "American Tourister", "American Tourister Ivy 55cm Cabin Trolley Bag", "Scratch-resistant polypropylene hardsided 4-wheel spinner luggage.", Decimal("2599.00"), Decimal("6500.00"), 4.7, 430, "https://images.unsplash.com/photo-1565026057447-bc90a3dceb87?w=600&auto=format&fit=crop&q=80", True),
        ("Travel", "Backpacks", "American Tourister", "American Tourister 32L Casual Laptop Backpack", "Water-resistant 3-compartment college & office bag with padded shoulder straps.", Decimal("1299.00"), Decimal("2700.00"), 4.6, 520, "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600&auto=format&fit=crop&q=80", True)
    ]

    idx = 100
    for cat, subcat, brand, name, desc, price, mrp, rating, rev_cnt, img, ext_comp in category_data:
        idx += 1
        gtin = None
        model_no = None
        sku = f"{brand[:3].upper()}-{idx}"
        
        offers = []
        if ext_comp:
            # Amazon Search Fallback
            offers.append({
                "store_domain": "amazon.in",
                "price": None,
                "mrp": None,
                "external_url": f"https://www.amazon.in/s?k={name.replace(' ', '+')}",
                "match_type": "SEARCH_FALLBACK",
                "confidence": 0.60,
                "reason": "Retailer search query fallback"
            })
            
            # Flipkart Search Fallback
            offers.append({
                "store_domain": "flipkart.com",
                "price": None,
                "mrp": None,
                "external_url": f"https://www.flipkart.com/search?q={name.replace(' ', '+')}",
                "match_type": "SEARCH_FALLBACK",
                "confidence": 0.60,
                "reason": "Retailer search query fallback"
            })

            # Myntra (for fashion/apparel/shoes) Search Fallback
            if cat in ["Sports & Fitness", "Fashion", "Apparel", "Footwear"]:
                offers.append({
                    "store_domain": "myntra.com",
                    "price": None,
                    "mrp": None,
                    "external_url": f"https://www.myntra.com/{name.lower().replace(' ', '-')[:40]}",
                    "match_type": "SEARCH_FALLBACK",
                    "confidence": 0.60,
                    "reason": "Retailer search query fallback"
                })

            # Brand Official Search Fallback
            if brand.lower() in ["nike", "adidas", "puma", "decathlon", "sony", "apple", "boat"]:
                if brand.lower() == "boat":
                    brand_domain = "boat-lifestyle.com"
                elif brand.lower() in ["nike", "puma", "apple"]:
                    brand_domain = f"{brand.lower()}.com"
                elif brand.lower() in ["adidas", "sony"]:
                    brand_domain = f"{brand.lower()}.co.in"
                else:
                    brand_domain = f"{brand.lower()}.in"
                offers.append({
                    "store_domain": brand_domain,
                    "price": None,
                    "mrp": None,
                    "external_url": f"https://www.{brand_domain}/search?q={name.replace(' ', '+')}",
                    "match_type": "SEARCH_FALLBACK",
                    "confidence": 0.60,
                    "reason": "Official Store search fallback"
                })

        item_dict = {
            "name": name,
            "description": desc,
            "brand": brand,
            "category": cat,
            "subcategory": subcat,
            "price": price,
            "mrp": mrp,
            "currency": "INR",
            "stock": 30 + (idx % 50),
            "gtin": gtin,
            "model_number": model_no,
            "sku": sku,
            "rating": rating,
            "review_count": rev_cnt,
            "tags": [cat.lower(), subcat.lower(), brand.lower(), "verified", "apex"],
            "image_url": img,
            "external_offers": offers
        }
        all_products.append(item_dict)

    return all_products
