import uuid
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models.revenue_opportunity import RevenueOpportunity
from app.database.models.policy import Policy
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.revenue.schemas import RevenueSimulationRequest, RevenueSimulationResponse
from app.services.audit_service import AuditService

class RevenueSimulator:
    """
    Deterministic Revenue Simulator:
    Simulates commercial outcomes and policy compliance for revenue proposals.
    
    Formula:
    - Incremental GMV = Target Orders * Unit Price
    - Discount Cost = (Incremental GMV * Discount Percent) / 100
    - Net Incremental Value = Incremental GMV - Discount Cost
    - Policy Compliance: Discount Percent <= Policy.max_discount_percent
    """

    @staticmethod
    def simulate(
        db: Session,
        merchant_id: str,
        req: RevenueSimulationRequest
    ) -> RevenueSimulationResponse:
        trace_id = req.trace_id or f"trc_sim_{uuid.uuid4().hex[:8]}"

        # 1. Fetch Opportunity
        opp = db.query(RevenueOpportunity).filter(
            RevenueOpportunity.id == req.opportunity_id,
            RevenueOpportunity.merchant_id == merchant_id
        ).first()

        if not opp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revenue opportunity '{req.opportunity_id}' not found for merchant."
            )

        # 2. Fetch Active Policy for max discount rule
        policy = db.query(Policy).filter(
            Policy.merchant_id == merchant_id,
            Policy.is_active == True
        ).order_by(Policy.version.desc()).first()

        max_allowed_discount = policy.max_discount_percent if policy else Decimal("5.00")

        # 3. Parameters
        discount_pct = req.discount_percent if req.discount_percent is not None else opp.proposed_discount_percent
        orders_count = req.target_orders if req.target_orders is not None else opp.estimated_incremental_orders

        # 4. Fetch Products for prices and inventory
        target_products = db.query(Product).filter(Product.id.in_(opp.target_product_ids)).all()
        if not target_products and opp.source_product_id:
            target_products = db.query(Product).filter(Product.id == opp.source_product_id).all()

        combined_unit_price = sum((p.price for p in target_products), Decimal("0.00"))
        if combined_unit_price == 0:
            combined_unit_price = Decimal("1000.00")

        # 5. Deterministic Calculations
        baseline_gmv = Decimal("100000.00") # Benchmark simulation baseline
        inc_gmv = combined_unit_price * Decimal(str(orders_count))
        discount_cost = (inc_gmv * discount_pct) / Decimal("100.00")
        net_value = inc_gmv - discount_cost
        projected_gmv = baseline_gmv + inc_gmv

        # 6. Inventory Impact
        inventory_consumption = {}
        stock_sufficient = True
        for p in target_products:
            stock = p.inventory.stock_quantity if p.inventory else 0
            inventory_consumption[p.name] = orders_count
            if stock < orders_count:
                stock_sufficient = False

        # 7. Deterministic Policy Compliance Check
        policy_compliant = True
        policy_details = f"Discount {discount_pct}% is within policy limit ({max_allowed_discount}%)."

        if discount_pct > max_allowed_discount:
            policy_compliant = False
            policy_details = f"POLICY VIOLATION: Proposed discount of {discount_pct}% exceeds maximum permitted policy threshold of {max_allowed_discount}%."
        elif not stock_sufficient:
            policy_compliant = False
            policy_details = "INVENTORY WARNING: Projected order volume exceeds current warehouse stock."

        risk_level = "HIGH" if not policy_compliant else ("MEDIUM" if discount_pct > Decimal("3.00") else "LOW")

        # Update opportunity state
        opp.proposed_discount_percent = discount_pct
        opp.estimated_incremental_orders = orders_count
        opp.estimated_incremental_gmv = inc_gmv
        opp.estimated_discount_cost = discount_cost
        opp.estimated_net_value = net_value
        opp.risk_level = risk_level
        opp.status = "SIMULATED"
        opp.simulation_payload = {
            "baseline_gmv": str(baseline_gmv),
            "projected_gmv": str(projected_gmv),
            "discount_cost": str(discount_cost),
            "net_incremental_value": str(net_value),
            "policy_compliant": policy_compliant,
            "policy_details": policy_details
        }
        db.commit()

        # Record Audit Event
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=trace_id,
            actor_type="SYSTEM",
            actor_id="RevenueSimulator",
            action="REVENUE_SIMULATED",
            event_type="SIMULATION",
            status="SUCCESS" if policy_compliant else "POLICY_BLOCKED",
            metadata_json={
                "opportunity_id": opp.id,
                "proposed_discount": str(discount_pct),
                "policy_max_discount": str(max_allowed_discount),
                "policy_compliant": policy_compliant,
                "projected_net_value": str(net_value)
            }
        )

        return RevenueSimulationResponse(
            opportunity_id=opp.id,
            baseline_gmv=baseline_gmv,
            projected_orders=orders_count,
            projected_gmv=projected_gmv,
            discount_cost=discount_cost,
            incremental_gmv=inc_gmv,
            net_incremental_value=net_value,
            inventory_consumption=inventory_consumption,
            policy_compliant=policy_compliant,
            policy_check_details=policy_details,
            risk_level=risk_level,
            is_simulated=True,
            simulation_label="SIMULATED — NOT ACTUAL REVENUE"
        )
