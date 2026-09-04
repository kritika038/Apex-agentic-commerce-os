import axios from 'axios';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (typeof window !== 'undefined' && error.response?.status === 401) {
      // Clear expired token only if request had an authorization header
      const authHeader = error.config?.headers?.Authorization;
      if (authHeader) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_profile');
      }
    }
    return Promise.reject(error);
  }
);

export function extractErrorMessage(err: unknown, fallback = 'An unexpected error occurred.'): string {
  if (!err) return fallback;
  if (typeof err === 'string') return err;

  const axiosErr = err as {
    response?: {
      data?: {
        detail?: string | Array<{ msg?: string; message?: string; loc?: string[] }> | Record<string, unknown>;
        message?: string;
        error?: string;
      };
      statusText?: string;
    };
    message?: string;
  };

  const data = axiosErr.response?.data;
  if (!data) {
    if (axiosErr.message) return axiosErr.message;
    return fallback;
  }

  if (typeof data.detail === 'string') {
    return data.detail;
  }

  if (Array.isArray(data.detail)) {
    const messages = data.detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          return item.msg || item.message || JSON.stringify(item);
        }
        return String(item);
      })
      .filter(Boolean);
    if (messages.length > 0) return messages.join(', ');
  }

  if (data.detail && typeof data.detail === 'object') {
    return (
      (data.detail as { message?: string; msg?: string }).message ||
      (data.detail as { message?: string; msg?: string }).msg ||
      JSON.stringify(data.detail)
    );
  }

  if (typeof data.message === 'string') return data.message;
  if (typeof data.error === 'string') return data.error;

  return fallback;
}


