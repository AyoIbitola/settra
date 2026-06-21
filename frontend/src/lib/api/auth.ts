import { apiRequest } from "./client";
import type { AuthResponse } from "./types";

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await apiRequest<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("settra_token", response.token);
  return response;
}

export async function register(email: string, business_name: string, password: string): Promise<AuthResponse> {
  const response = await apiRequest<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, business_name, password }),
  });
  localStorage.setItem("settra_token", response.token);
  return response;
}

export async function getMe(): Promise<AuthResponse["user"]> {
  return apiRequest<AuthResponse["user"]>("/auth/me");
}

export function logout() {
  localStorage.removeItem("settra_token");
}
