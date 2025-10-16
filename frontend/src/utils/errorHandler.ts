/**
 * Extracts a user-friendly error message from various error response formats
 */
export const extractErrorMessage = (error: any): string => {
  // Handle axios error responses
  if (error?.response?.data) {
    const data = error.response.data;
    
    // Handle FastAPI validation errors (422)
    if (error.response.status === 422 && data.detail) {
      // If detail is an array of validation errors
      if (Array.isArray(data.detail)) {
        // Extract the first error message
        const firstError = data.detail[0];
        if (firstError?.msg) {
          // Format field name and message
          const field = firstError.loc?.join('.') || 'field';
          return `${field}: ${firstError.msg}`;
        }
        // If it has a different structure, try to stringify it
        return JSON.stringify(firstError);
      }
      // If detail is a string
      if (typeof data.detail === 'string') {
        return data.detail;
      }
      // If detail is an object
      if (typeof data.detail === 'object') {
        return JSON.stringify(data.detail);
      }
    }
    
    // Handle regular error messages
    if (typeof data.detail === 'string') {
      return data.detail;
    }
    
    // Handle message field
    if (typeof data.message === 'string') {
      return data.message;
    }
    
    // Handle error field
    if (typeof data.error === 'string') {
      return data.error;
    }
    
    // If data is a string itself
    if (typeof data === 'string') {
      return data;
    }
    
    // Fallback to stringifying the data
    try {
      return JSON.stringify(data);
    } catch {
      return 'An unexpected error occurred';
    }
  }
  
  // Handle regular Error objects
  if (error?.message) {
    return error.message;
  }
  
  // Handle string errors
  if (typeof error === 'string') {
    return error;
  }
  
  // Fallback
  return 'An unexpected error occurred';
};

/**
 * Formats validation errors into a user-friendly message
 */
export const formatValidationErrors = (errors: any[]): string => {
  if (!Array.isArray(errors)) {
    return extractErrorMessage(errors);
  }
  
  const messages = errors.map(error => {
    if (error?.msg && error?.loc) {
      const field = error.loc[error.loc.length - 1] || 'field';
      return `${field}: ${error.msg}`;
    }
    if (error?.msg) {
      return error.msg;
    }
    if (typeof error === 'string') {
      return error;
    }
    return JSON.stringify(error);
  });
  
  return messages.join(', ');
};