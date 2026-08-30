export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, unknown>[] | null;

  constructor(
    status: number,
    code: string,
    message: string,
    fields: Record<string, unknown>[] | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

export class ApiConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiConfigError";
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.status >= 500) {
      return "An unexpected error occurred. Please try again.";
    }
    return error.message;
  }
  if (error instanceof ApiConfigError) {
    return error.message;
  }
  if (error instanceof Error && error.name === "TimeoutError") {
    return "The request timed out. Please try again.";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unexpected error occurred. Please try again.";
}
