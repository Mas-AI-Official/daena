/**
 * Daena AI VP JavaScript/TypeScript SDK
 * 
 * Official SDK for integrating with Daena AI VP System.
 */

export { DaenaClient } from './client';
export {
  DaenaAPIError,
  DaenaAuthenticationError,
  DaenaRateLimitError,
  DaenaNotFoundError,
  DaenaValidationError,
  DaenaTimeoutError
} from './exceptions';
export {
  Agent,
  Department,
  MemoryRecord,
  CouncilDecision,
  ExperienceVector,
  SystemMetrics
} from './models';

export const SDK_VERSION = '1.0.0';

