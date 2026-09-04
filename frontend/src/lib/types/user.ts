export interface UserProfile {
  id: string;
  email: string;
  full_name?: string;
  role: 'customer' | 'merchant_admin' | string;
  avatar_url?: string;
}
