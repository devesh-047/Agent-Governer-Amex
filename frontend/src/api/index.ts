/**
 * API exports
 *
 * Phase 1: Using mocks for independent frontend development
 * Phase 2+: Swap to real fetch-based client when D1/D2 endpoints are ready
 */

import { mockApi } from './mocks';
import type { GovernanceApi } from './client';

// Phase 1-2: Use mocks
// TODO: Swap to real client when backend is ready
export const api: GovernanceApi = mockApi;

// Re-export types for convenience
export * from './types';
export * from './client';
