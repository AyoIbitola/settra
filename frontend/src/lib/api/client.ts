import { mockRequest } from "./mocks/mockHandlers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

export interface ApiError {
  message: string;
  status: number;
  data?: any;
}

function getAuthToken(): string | null {
  return localStorage.getItem("settra_token");
}

async function buildApiError(response: Response): Promise<ApiError> {
  const data = await response.json().catch(() => ({}));
  
  let msg = "An unexpected error occurred";
  if (Array.isArray(data.detail)) {
    // FastAPI validation error array
    msg = data.detail.map((e: any) => `${e.loc?.join(".")}: ${e.msg}`).join(", ");
  } else if (typeof data.detail === "string") {
    msg = data.detail;
  } else if (data.message) {
    msg = data.message;
  }

  return {
    message: msg,
    status: response.status,
    data,
  };
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  // SPECIAL EXCEPTION: Milestone 6 Paid Transition Simulation
  // The backend doesn't have Bitnob webhooks wired up yet for real payments.
  // We use the mock layer for public status polling if explicitly requested 
  // via a specific flag or in development for that exact slice.
  const isPaidSimulation = path.includes("/status") && USE_MOCKS;

  if (USE_MOCKS || isPaidSimulation) {
    console.log(`[MOCK API] ${options.method || 'GET'} ${path}`);
    return mockRequest<T>(path, options);
  }

  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await buildApiError(response);
    console.error(`[API ERROR] ${options.method || 'GET'} ${path}`, error);
    throw error;
  }

  return response.json();
}
