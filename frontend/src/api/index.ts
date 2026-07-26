/**
 * API exports
 *
 * Phase 1: Using mocks for independent frontend development
 * Phase 2+: Swap to real fetch-based client when D1/D2 endpoints are ready
 */

import type { GovernanceApi } from './client';
import { fetchApi } from './fetchClient';
// Keep mock import commented out or available for quick rollback if needed
// import { mockApi } from './mocks';

/**
 * Singleton API client instance used by all components.
 *
 * During Phase 1-2, this was mockApi.
 * Switched to real fetchApi for Phase 3+.
 */
export const api: GovernanceApi = fetchApi;

// Re-export types for convenience
export * from './types';
export * from './client';
