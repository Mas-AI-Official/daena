package daena

import "fmt"

// DaenaError is the base error type for Daena SDK errors
type DaenaError struct {
	Message    string
	StatusCode int
	ErrorType  string
}

func (e *DaenaError) Error() string {
	return fmt.Sprintf("Daena API error (%s): %s (status: %d)", e.ErrorType, e.Message, e.StatusCode)
}

// AuthenticationError represents authentication failures
type AuthenticationError struct {
	DaenaError
}

// NotFoundError represents resource not found errors
type NotFoundError struct {
	DaenaError
}

// RateLimitError represents rate limit errors
type RateLimitError struct {
	DaenaError
	RetryAfter int // seconds
}

// ValidationError represents validation errors
type ValidationError struct {
	DaenaError
}

// APIError represents generic API errors
type APIError struct {
	DaenaError
}

// NewAuthenticationError creates a new authentication error
func NewAuthenticationError(message string) *AuthenticationError {
	return &AuthenticationError{
		DaenaError: DaenaError{
			Message:   message,
			ErrorType: "authentication",
		},
	}
}

// NewNotFoundError creates a new not found error
func NewNotFoundError(message string) *NotFoundError {
	return &NotFoundError{
		DaenaError: DaenaError{
			Message:   message,
			ErrorType: "not_found",
		},
	}
}

// NewRateLimitError creates a new rate limit error
func NewRateLimitError(message string, retryAfter int) *RateLimitError {
	return &RateLimitError{
		DaenaError: DaenaError{
			Message:   message,
			ErrorType: "rate_limit",
		},
		RetryAfter: retryAfter,
	}
}

// NewValidationError creates a new validation error
func NewValidationError(message string) *ValidationError {
	return &ValidationError{
		DaenaError: DaenaError{
			Message:   message,
			ErrorType: "validation",
		},
	}
}

