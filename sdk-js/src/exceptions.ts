/**
 * Exception classes for Daena SDK.
 */

export class DaenaAPIError extends Error {
  public readonly statusCode?: number;
  public readonly response?: any;

  constructor(message: string, statusCode?: number, response?: any) {
    super(message);
    this.name = 'DaenaAPIError';
    this.statusCode = statusCode;
    this.response = response;
    Object.setPrototypeOf(this, DaenaAPIError.prototype);
  }
}

export class DaenaAuthenticationError extends DaenaAPIError {
  constructor(message: string = 'Authentication failed. Please check your API key.', statusCode?: number, response?: any) {
    super(message, statusCode, response);
    this.name = 'DaenaAuthenticationError';
    Object.setPrototypeOf(this, DaenaAuthenticationError.prototype);
  }
}

export class DaenaRateLimitError extends DaenaAPIError {
  public readonly retryAfter?: number;

  constructor(message: string = 'Rate limit exceeded. Please try again later.', retryAfter?: number, statusCode?: number, response?: any) {
    super(message, statusCode, response);
    this.name = 'DaenaRateLimitError';
    this.retryAfter = retryAfter;
    Object.setPrototypeOf(this, DaenaRateLimitError.prototype);
  }
}

export class DaenaNotFoundError extends DaenaAPIError {
  constructor(message: string = 'Resource not found.', statusCode?: number, response?: any) {
    super(message, statusCode, response);
    this.name = 'DaenaNotFoundError';
    Object.setPrototypeOf(this, DaenaNotFoundError.prototype);
  }
}

export class DaenaValidationError extends DaenaAPIError {
  constructor(message: string = 'Request validation failed.', statusCode?: number, response?: any) {
    super(message, statusCode, response);
    this.name = 'DaenaValidationError';
    Object.setPrototypeOf(this, DaenaValidationError.prototype);
  }
}

export class DaenaTimeoutError extends DaenaAPIError {
  constructor(message: string = 'Request timed out.', statusCode?: number, response?: any) {
    super(message, statusCode, response);
    this.name = 'DaenaTimeoutError';
    Object.setPrototypeOf(this, DaenaTimeoutError.prototype);
  }
}

