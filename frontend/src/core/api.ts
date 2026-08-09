const API_ROOT = "/api/v1";
const SESSION_EXPIRED_MESSAGE = "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";

type AccessTokenRecovery = (failedAccessToken: string) => Promise<string | null>;

let accessTokenRecovery: AccessTokenRecovery | null = null;
let recoveryInFlight: Promise<string | null> | null = null;

export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly code?: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * App owns the refresh-token lifecycle while this API layer coordinates retries.
 * A shared in-flight promise prevents concurrent 401 responses from rotating the
 * same refresh token more than once.
 */
export function configureAccessTokenRecovery(handler: AccessTokenRecovery | null) {
  accessTokenRecovery = handler;
  if (!handler) recoveryInFlight = null;

  return () => {
    if (accessTokenRecovery === handler) accessTokenRecovery = null;
  };
}

function apiUrl(path: string) {
  return path.startsWith("/ai/") ? path : API_ROOT + path;
}

function requestHeaders(token: string | undefined, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  const isForm = init?.body instanceof FormData;

  if (!isForm && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

function fetchApi(path: string, token?: string, init?: RequestInit) {
  return fetch(apiUrl(path), {
    ...init,
    headers: requestHeaders(token, init),
  });
}

async function recoverAccessToken(failedAccessToken: string) {
  if (!accessTokenRecovery) return null;

  if (!recoveryInFlight) {
    recoveryInFlight = accessTokenRecovery(failedAccessToken)
      .catch(() => null)
      .finally(() => {
        recoveryInFlight = null;
      });
  }

  return recoveryInFlight;
}

async function retryAfterUnauthorized(path: string, token: string | undefined, init?: RequestInit) {
  let response = await fetchApi(path, token, init);
  if (response.status !== 401 || !token || !accessTokenRecovery) return response;

  const renewedAccessToken = await recoverAccessToken(token);
  if (!renewedAccessToken) {
    throw new ApiError(SESSION_EXPIRED_MESSAGE, 401, "SESSION_EXPIRED");
  }

  // Retry exactly once. A second 401 means the renewed session is not usable.
  response = await fetchApi(path, renewedAccessToken, init);
  if (response.status === 401) {
    throw new ApiError(SESSION_EXPIRED_MESSAGE, 401, "SESSION_EXPIRED");
  }
  return response;
}

async function readApiError(response: Response, fallback: string) {
  const body = await response.json().catch(() => ({ detail: fallback })) as { detail?: string; code?: string };
  return new ApiError(body.detail || fallback, response.status, body.code);
}

export async function request<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const response = await retryAfterUnauthorized(path, token, init);

  if (!response.ok) {
    throw await readApiError(response, "Không thể kết nối dịch vụ.");
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function requestBlob(path: string, token?: string): Promise<Blob> {
  const response = await retryAfterUnauthorized(path, token);
  if (!response.ok) {
    throw await readApiError(response, `HTTP ${response.status}`);
  }
  return response.blob();
}
