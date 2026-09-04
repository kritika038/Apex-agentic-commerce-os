export interface DeliveryAddressSnapshot {
  full_name: string;
  phone: string;
  email: string;
  address_line1: string;
  address_line2?: string;
  landmark?: string;
  city: string;
  state: string;
  pin_code: string;
  country: string;
}

export interface OrderItemSnapshot {
  product_id: string;
  name: string;
  category?: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
  image_url?: string;
}

export interface OrderPaymentSnapshot {
  method: string;
  status: string;
  razorpay_order_id?: string;
  razorpay_payment_id?: string;
  paid_at?: string;
}

export interface OrderPriceSummarySnapshot {
  subtotal: number;
  delivery_charges: number;
  taxes: number;
  discount: number;
  coupon_discount?: number;
  coins_discount?: number;
  coin_discount?: number;
  total_amount: number;
  currency: string;
}

export interface OrderTimelineStepSnapshot {
  title: string;
  status: 'COMPLETED' | 'CURRENT' | 'PENDING' | 'FAILED' | 'UNAVAILABLE';
  timestamp?: string;
  description?: string;
}

export interface OrderData {
  id: string;
  order_number: string;
  purchase_intent_id: string;
  created_at: string;
  status: 'CONFIRMED' | 'PROCESSING' | 'FAILED' | 'CANCELLED' | 'DELIVERED' | 'RETURN_REQUESTED' | 'RETURNED';
  total_amount: number;
  currency: string;
  items: OrderItemSnapshot[];
  payment: OrderPaymentSnapshot;
  price_summary: OrderPriceSummarySnapshot;
  delivery_address?: DeliveryAddressSnapshot;
  timeline: OrderTimelineStepSnapshot[];
}

export interface BuyAgainResult {
  success: boolean;
  added_items: Array<{
    product_id: string;
    name: string;
    quantity: number;
    current_price: number;
    historical_price: number;
  }>;
  unavailable_items: Array<{
    product_id: string;
    name: string;
    reason: string;
  }>;
  cart: {
    items: Array<{
      product_id: string;
      name: string;
      quantity: number;
      unit_price: number;
      subtotal: number;
      image_url?: string;
    }>;
    total_amount: number;
    currency: string;
  };
  message: string;
}
