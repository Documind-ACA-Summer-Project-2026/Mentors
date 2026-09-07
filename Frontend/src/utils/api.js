/**
 * Enhanced API utility with retry logic, error handling, and timeout management
 */

// Configuration
const API_CONFIG = {
  MAX_RETRIES: 3,
  INITIAL_RETRY_DELAY: 1000, // ms
  MAX_RETRY_DELAY: 5000, // ms
  TIMEOUT: 30000, // ms
  BACKOFF_MULTIPLIER: 2,
};

class APIError extends Error {
  constructor(message, statusCode, errorCode, originalError) {
    super(message);
    this.name = "APIError";
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.originalError = originalError;
  }

  isNetworkError() {
    return this.statusCode === 0 || this.statusCode === undefined;
  }

  isServerError() {
    return this.statusCode >= 500;
  }

  isClientError() {
    return this.statusCode >= 400 && this.statusCode < 500;
  }

  isAuthError() {
    return this.statusCode === 401;
  }

  isTimeoutError() {
    return this.originalError?.name === "TimeoutError";
  }
}

/**
 * Make a fetch request with timeout
 */
function fetchWithTimeout(url, options = {}, timeout = API_CONFIG.TIMEOUT) {
  return Promise.race([
    fetch(url, options),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error("TimeoutError")), timeout)
    ),
  ]);
}

/**
 * Determine if an error is retryable
 */
function isRetryableError(error) {
  // Network errors are retryable
  if (error.isNetworkError && error.isNetworkError()) {
    return true;
  }

  // Timeout errors are retryable
  if (error.isTimeoutError && error.isTimeoutError()) {
    return true;
  }

  // Server errors (5xx) are retryable
  if (error.isServerError && error.isServerError()) {
    return true;
  }

  // Specific status codes that are retryable
  const retryableStatuses = [408, 429, 503, 504];
  return retryableStatuses.includes(error.statusCode);
}

/**
 * Calculate exponential backoff delay
 */
function calculateBackoffDelay(attempt) {
  const delay = Math.min(
    API_CONFIG.INITIAL_RETRY_DELAY * Math.pow(API_CONFIG.BACKOFF_MULTIPLIER, attempt),
    API_CONFIG.MAX_RETRY_DELAY
  );
  // Add jitter to prevent thundering herd
  const jitter = Math.random() * 0.1 * delay;
  return delay + jitter;
}

/**
 * Core API call with retry logic
 */
export const apiCall = async (endpoint, options = {}) => {
  let lastError;
  let attempt = 0;

  while (attempt < API_CONFIG.MAX_RETRIES) {
    try {
      const headers = {
        "Content-Type": "application/json",
        ...options.headers,
      };

      const response = await fetchWithTimeout(
        endpoint,
        {
          ...options,
          headers,
          credentials: "same-origin",
        },
        options.timeout || API_CONFIG.TIMEOUT
      );

      // Handle authentication errors - don't retry
      if (response.status === 401) {
        const errorData = await response.json().catch(() => ({}));
        const error = new APIError(
          "Unauthorized - please log in again",
          401,
          "AUTH_ERROR",
          null
        );
        throw error;
      }

      // Handle other HTTP errors
      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch {
          errorData = { detail: `HTTP ${response.status}` };
        }

        const error = new APIError(
          errorData.message || errorData.detail || `API call failed: ${response.status}`,
          response.status,
          errorData.error || `HTTP_${response.status}`,
          null
        );

        // Check if error is retryable
        if (isRetryableError(error) && attempt < API_CONFIG.MAX_RETRIES - 1) {
          lastError = error;
          attempt++;
          const delay = calculateBackoffDelay(attempt - 1);
          console.warn(
            `API call failed with status ${response.status}. Retrying in ${Math.round(delay)}ms... (attempt ${attempt}/${API_CONFIG.MAX_RETRIES})`
          );
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }

        throw error;
      }

      // Success - parse and return response
      try {
        const data = await response.json();
        return data;
      } catch (parseError) {
        throw new APIError(
          "Failed to parse server response",
          response.status,
          "PARSE_ERROR",
          parseError
        );
      }
    } catch (error) {
      // Handle timeout errors
      if (error.message === "TimeoutError") {
        const apiError = new APIError(
          "Request timed out. The server is not responding.",
          0,
          "TIMEOUT_ERROR",
          error
        );

        if (attempt < API_CONFIG.MAX_RETRIES - 1) {
          lastError = apiError;
          attempt++;
          const delay = calculateBackoffDelay(attempt - 1);
          console.warn(
            `Request timed out. Retrying in ${Math.round(delay)}ms... (attempt ${attempt}/${API_CONFIG.MAX_RETRIES})`
          );
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }

        throw apiError;
      }

      // Handle network errors
      if (error instanceof TypeError && error.message.includes("Failed to fetch")) {
        const apiError = new APIError(
          "Network error - server is not reachable. Please check your connection.",
          0,
          "NETWORK_ERROR",
          error
        );

        if (attempt < API_CONFIG.MAX_RETRIES - 1) {
          lastError = apiError;
          attempt++;
          const delay = calculateBackoffDelay(attempt - 1);
          console.warn(
            `Network error. Retrying in ${Math.round(delay)}ms... (attempt ${attempt}/${API_CONFIG.MAX_RETRIES})`
          );
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }

        throw apiError;
      }

      // If it's already an APIError, rethrow it
      if (error instanceof APIError) {
        throw error;
      }

      // Handle other unexpected errors
      const apiError = new APIError(
        error.message || "An unexpected error occurred",
        0,
        "UNKNOWN_ERROR",
        error
      );

      if (attempt < API_CONFIG.MAX_RETRIES - 1 && isRetryableError(apiError)) {
        lastError = apiError;
        attempt++;
        const delay = calculateBackoffDelay(attempt - 1);
        console.warn(
          `Error occurred. Retrying in ${Math.round(delay)}ms... (attempt ${attempt}/${API_CONFIG.MAX_RETRIES})`
        );
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }

      throw apiError;
    }
  }

  // All retries exhausted
  if (lastError) {
    throw lastError;
  }

  throw new APIError(
    "API call failed after multiple retries",
    0,
    "MAX_RETRIES_EXCEEDED",
    null
  );
};

/**
 * POST request with cookie authentication
 */
export const apiPost = (endpoint, body, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: "POST",
    body: JSON.stringify(body),
  });
};

/**
 * GET request with cookie authentication
 */
export const apiGet = (endpoint, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: "GET",
  });
};

/**
 * PUT request with cookie authentication
 */
export const apiPut = (endpoint, body, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: "PUT",
    body: JSON.stringify(body),
  });
};

/**
 * DELETE request with cookie authentication
 */
export const apiDelete = (endpoint, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: "DELETE",
  });
};

/**
 * Extract user-friendly error message
 */
export const getErrorMessage = (error) => {
  if (!error) {
    return "An unexpected error occurred";
  }

  if (error instanceof APIError) {
    if (error.isNetworkError()) {
      return "Server is not reachable. Please check your internet connection.";
    }

    if (error.isTimeoutError()) {
      return "Request timed out. The server is taking too long to respond.";
    }

    if (error.isAuthError()) {
      return "Your session has expired. Please log in again.";
    }

    if (error.isServerError()) {
      return "Server error. Please try again later.";
    }

    if (error.isClientError()) {
      return error.message;
    }

    return error.message || "An error occurred";
  }

  return error.message || error.toString() || "An unexpected error occurred";
};

/**
 * Check if error is retriable
 */
export const isRetriableError = (error) => {
  if (error instanceof APIError) {
    return isRetryableError(error);
  }
  return false;
};

export { APIError };
