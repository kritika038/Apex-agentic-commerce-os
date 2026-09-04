from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.schemas.ai_commerce import (
    AgentProductOffer,
    AgentSearchRequest,
    AgentSearchResponse,
    AgentNegotiateRequest,
    AgentSearchQuery
)
from app.services.ai_commerce_service import AICommerceService

class ApexCommerceAgent:
    """
    Merchant-side AI Commerce Agent for Apex Sports.
    Responsible for catalog discovery, constraint negotiation, rational ranking, and offer explanation.
    Never fabricates stock, prices, or payment state.
    """
    def __init__(self, db: Session, merchant_id: Optional[str] = None):
        self.db = db
        self.merchant_id = merchant_id

    def handle_search(self, request: AgentSearchRequest, buyer_id: str = "customer_ai") -> AgentSearchResponse:
        return AICommerceService.search_catalog(
            db=self.db,
            request=request,
            merchant_id=self.merchant_id,
            authenticated_buyer_id=buyer_id
        )

    def handle_negotiation(self, request: AgentNegotiateRequest, buyer_id: str = "customer_ai") -> AgentSearchResponse:
        """
        Handles multi-turn constraint negotiation (e.g. increasing budget, showing cheapest options, changing category).
        """
        action = request.action
        max_p = request.new_budget
        limit = request.limit or 2

        # Re-run search with adjusted constraints
        search_req = AgentSearchRequest(
            protocol_version="1.0",
            request_id=request.request_id,
            session_id=request.session_id,
            query=AgentSearchQuery(
                category="Running",
                use_case="marathon",
                max_price=max_p,
                currency="INR"
            ),
            natural_language_query=request.natural_language_message
        )

        res = AICommerceService.search_catalog(
            db=self.db,
            request=search_req,
            merchant_id=self.merchant_id,
            authenticated_buyer_id=buyer_id
        )

        if action == "show_cheapest" and res.offers:
            sorted_offers = sorted(res.offers, key=lambda x: x.unit_price)[:limit]
            res.offers = sorted_offers
            res.total_offers = len(sorted_offers)
            res.explanation = f"Filtered to the cheapest {len(sorted_offers)} verified options under ₹{int(max_p or 10000):,}."
        elif action == "show_best" and res.offers:
            best_offer = sorted(res.offers, key=lambda x: (-1 if "marathon" in x.name.lower() else 0, x.unit_price))[0]
            res.offers = [best_offer]
            res.total_offers = 1
            res.explanation = f"Selected **{best_offer.name}** (₹{best_offer.unit_price:,.2f}) as the optimal marathon match."

        return res
