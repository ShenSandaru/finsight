import { apiClient } from "./client";

export interface User {
  id: string;
  email: string;
  name: string;
  image_url?: string | null;
  provider: string;
  provider_sub: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export async function getCurrentUser(): Promise<User> {
  return apiClient<User>("/api/v1/auth/me");
}

export async function logout(): Promise<{ message: string }> {
  return apiClient<{ message: string }>("/api/v1/auth/logout", {
    method: "POST",
  });
}
