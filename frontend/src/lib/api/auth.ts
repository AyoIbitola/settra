import { apiRequest } from "./client";
import type { TokenResponse, UserResponse } from "./types";

export async function login(email: string, password: string): Promise<UserResponse> {
  const response = await apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("settra_token", response.access_token);
  return getMe();
}

export async function register(email: string, business_name: string, password: string): Promise<UserResponse> {
  const response = await apiRequest<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, business_name, password }),
  });
  localStorage.setItem("settra_token", response.access_token);
  return getMe();
}

export async function getMe(): Promise<UserResponse> {
  return apiRequest<UserResponse>("/auth/me");
}

export function logout() {
  localStorage.removeItem("settra_token");
}
