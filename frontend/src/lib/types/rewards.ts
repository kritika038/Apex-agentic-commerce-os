export interface CouponData {
  code: string;
  description: string;
  discount_type: 'FIXED' | 'PERCENTAGE';
  discount_value: number;
  min_cart_amount: number;
  max_discount_amount?: number;
  is_active: boolean;
  expires_at?: string;
}

export interface VoucherData {
  id: string;
  code: string;
  title: string;
  description: string;
  discount_type: 'FIXED' | 'PERCENTAGE';
  discount_value: number;
  min_cart_amount: number;
  max_discount_amount?: number;
  expires_at: string;
  status: 'AVAILABLE' | 'USED' | 'EXPIRED';
}

export interface CartPricingBreakdown {
  subtotal: number;
  coupon_code?: string | null;
  coupon_discount: number;
  voucher_code?: string | null;
  voucher_discount: number;
  coins_used: number;
  coin_discount: number;
  delivery_charges: number;
  taxes: number;
  total: number;
  currency: string;
  points_to_earn: number;
  available_coin_balance: number;
  max_coins_redeemable: number;
  coin_value_inr: number;
}

export interface CoinLedgerItem {
  id: string;
  amount: number;
  transaction_type: string;
  reference_id?: string;
  description: string;
  created_at: string;
}

export interface RewardPointsLedgerItem {
  id: string;
  points: number;
  transaction_type: string;
  reference_id?: string;
  description: string;
  created_at: string;
}

export interface CustomerRewardsData {
  coin_balance: number;
  estimated_coin_value_inr: number;
  points_balance: number;
  conversion_rate_description: string;
  earning_rule_description: string;
  available_vouchers: VoucherData[];
  coin_history: CoinLedgerItem[];
  points_history: RewardPointsLedgerItem[];
}
