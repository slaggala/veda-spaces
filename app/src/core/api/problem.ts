/** RFC 9457 problem details as returned by the Veda API (08 §2.4). */
export interface FieldError {
  field: string;
  code: string;
  message?: string;
}

export class ApiProblem extends Error {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail?: string;
  readonly errors: FieldError[];
  readonly requestId?: string;
  /** The complete problem body, including extension members such as current_version, kind, mfa_token. */
  readonly body: Record<string, unknown>;

  constructor(status: number, body: Record<string, unknown>, requestId?: string) {
    const code = typeof body.code === 'string' ? body.code : status >= 500 ? 'INTERNAL_ERROR' : 'UNKNOWN_ERROR';
    const title = typeof body.title === 'string' ? body.title : 'Request failed';
    super(typeof body.detail === 'string' ? body.detail : title);
    this.name = 'ApiProblem';
    this.status = status;
    this.code = code;
    this.title = title;
    this.detail = typeof body.detail === 'string' ? body.detail : undefined;
    this.errors = Array.isArray(body.errors) ? (body.errors as FieldError[]).filter((e) => e && typeof e.field === 'string') : [];
    this.requestId = typeof body.request_id === 'string' ? body.request_id : requestId;
    this.body = body;
  }

  /** Extension member accessor, e.g. problem.ext<number>('current_version'). */
  ext<T = unknown>(key: string): T | undefined {
    return this.body[key] as T | undefined;
  }

  fieldError(field: string): FieldError | undefined {
    return this.errors.find((e) => e.field === field);
  }

  get isNetwork(): boolean {
    return this.code === 'NETWORK_ERROR';
  }
}

/**
 * Parse a non-2xx fetch Response into an ApiProblem. Tolerates non-JSON bodies (proxies, 502 pages):
 * those become a generic problem that still carries the request id from X-Request-ID.
 */
export async function parseProblem(response: Response): Promise<ApiProblem> {
  const requestId = response.headers.get('X-Request-ID') ?? undefined;
  let body: Record<string, unknown> = {};
  try {
    const text = await response.text();
    if (text) {
      const parsed: unknown = JSON.parse(text);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) body = parsed as Record<string, unknown>;
    }
  } catch {
    body = {};
  }
  if (!body.code) {
    body = {
      ...body,
      code: response.status === 429 ? 'RATE_LIMITED' : response.status >= 500 ? 'INTERNAL_ERROR' : `HTTP_${response.status}`,
      title: body.title ?? (response.statusText || 'Request failed'),
    };
  }
  return new ApiProblem(response.status, body, requestId);
}

export function networkProblem(error: unknown): ApiProblem {
  return new ApiProblem(0, {
    code: 'NETWORK_ERROR',
    title: 'Network error',
    detail: error instanceof Error ? error.message : 'The server could not be reached.',
  });
}
