export interface TryOnEligibilityResponse {
  supported: boolean;
  product_id: string;
  product_name: string;
  garment_type?: 'CLOTHING' | 'FOOTWEAR' | string;
  category?: string;
  subcategory?: string;
  reason: string;
  recommended_photo_type: string;
  product_image_url?: string;
  color?: string;
  size?: string;
}

export interface StyleRecommendationItem {
  product_id: string;
  name: string;
  brand?: string;
  price: number;
  mrp?: number;
  category: string;
  subcategory?: string;
  image_url?: string;
  styling_reason: string;
  vto_eligible?: boolean;
}

export interface TryOnJobStatusResponse {
  job_id: string;
  status: 'CREATED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'EXPIRED' | 'CANCELLED';
  progress_percent?: number;
  processing_stage?: 'PREPARING' | 'GARMENT_VALIDATION' | 'POSE_DETECTION' | 'GARMENT_PREPARATION' | 'DIFFUSION' | 'FINALIZING' | 'COMPLETED' | 'FAILED' | string;
  progress_message?: string;
  sampling_step?: number | null;
  sampling_total?: number | null;
  product_id: string;
  product_name: string;
  variant_id?: string;
  garment_type: string;
  provider: string;
  is_demo: boolean;
  disclaimer: string;
  preview_image_url?: string;
  original_product_image_url: string;
  error_code?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  expires_at: string;
  complete_the_look: StyleRecommendationItem[];
}
