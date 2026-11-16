import { t } from "../i18n";
import { getLang } from "../lib/lang";
/** Thin fetch wrapper: bearer token, JSON, typed errors. No business logic here. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

type TokenProvider = () => string | null;
type UnauthorizedHandler = () => void;
type AuthHeader = (token: string) => Record<string, string>;

/** Back-office users send a bearer token; paired phones send their device token. */
export const bearer: AuthHeader = (token) => ({ Authorization: `Bearer ${token}` });
export const deviceHeader: AuthHeader = (token) => ({ "X-Device-Token": token });

export class ApiClient {
  constructor(
    private readonly getToken: TokenProvider,
    private readonly onUnauthorized: UnauthorizedHandler,
    private readonly baseUrl = "/api",
    private readonly authHeader: AuthHeader = bearer,
  ) {}

  get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  put<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("PUT", path, body);
  }

  patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("PATCH", path, body);
  }

  async delete(path: string): Promise<void> {
    await this.send("DELETE", path);
  }

  /** Multipart upload (Excel import). The browser sets the boundary header itself. */
  async upload<T>(path: string, form: FormData): Promise<T> {
    const response = await this.send("POST", path, form);
    return (await response.json()) as T;
  }

  /** Multipart upload answered by a file (refused rows of an import). */
  async uploadBlob(path: string, form: FormData): Promise<Blob> {
    return (await this.send("POST", path, form)).blob();
  }

  /** Binary download (QR image, CSV export). */
  async blob(path: string): Promise<Blob> {
    return (await this.send("GET", path)).blob();
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const response = await this.send(method, path, body);
    if (response.status === 204) return undefined as T; // "No Content": nothing to parse
    return (await response.json()) as T;
  }

  private async send(method: string, path: string, body?: unknown): Promise<Response> {
    const headers: Record<string, string> = {};
    const token = this.getToken();
    if (token) Object.assign(headers, this.authHeader(token));
    const isForm = body instanceof FormData;
    if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
    headers["Accept-Language"] = getLang(); // the server answers its messages in this language

    let response: Response;
    try {
      response = await fetch(this.baseUrl + path, {
        method,
        headers,
        body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, t("net.unreachable"));
    }

    if (response.status === 401 && token) this.onUnauthorized();
    if (!response.ok) throw new ApiError(response.status, await this.messageOf(response));
    return response;
  }

  private async messageOf(response: Response): Promise<string> {
    try {
      const data = await response.json();
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail)) return t("net.invalid");
    } catch {
      /* body was not JSON */
    }
    return t("net.error", { status: response.status });
  }
}
