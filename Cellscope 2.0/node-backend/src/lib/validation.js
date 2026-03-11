import { HttpError } from './errors.js';

const PROJECT_TYPES = new Set(['Cathode', 'Anode', 'Full Cell']);

export function getProjectType(value, { required = false } = {}) {
  if (value === undefined || value === null || value === '') {
    if (required) {
      throw new HttpError(400, 'project_type is required');
    }
    return null;
  }

  const normalized = String(value).trim();
  if (!PROJECT_TYPES.has(normalized)) {
    throw new HttpError(400, "project_type must be one of 'Cathode', 'Anode', or 'Full Cell'");
  }
  return normalized;
}

export function requiredString(value, fieldName, maxLength = 255) {
  if (value === undefined || value === null) {
    throw new HttpError(400, `${fieldName} is required`);
  }

  const normalized = String(value).trim();
  if (!normalized) {
    throw new HttpError(400, `${fieldName} cannot be empty`);
  }

  if (normalized.length > maxLength) {
    throw new HttpError(400, `${fieldName} exceeds max length ${maxLength}`);
  }

  return normalized;
}

export function optionalString(value, fieldName, maxLength = 2000) {
  if (value === undefined || value === null || value === '') {
    return null;
  }

  const normalized = String(value).trim();
  if (normalized.length > maxLength) {
    throw new HttpError(400, `${fieldName} exceeds max length ${maxLength}`);
  }

  return normalized;
}

export function optionalNumber(value, fieldName) {
  if (value === undefined || value === null || value === '') {
    return null;
  }

  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    throw new HttpError(400, `${fieldName} must be a number`);
  }

  return parsed;
}

export function optionalInteger(value, fieldName) {
  if (value === undefined || value === null || value === '') {
    return null;
  }

  const parsed = Number(value);
  if (!Number.isInteger(parsed)) {
    throw new HttpError(400, `${fieldName} must be an integer`);
  }

  return parsed;
}

export function optionalBoolean(value) {
  if (value === undefined || value === null || value === '') {
    return null;
  }

  if (typeof value === 'boolean') {
    return value;
  }

  if (typeof value === 'number') {
    if (value === 1) {
      return true;
    }
    if (value === 0) {
      return false;
    }
  }

  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (normalized === 'true' || normalized === '1' || normalized === 'yes') {
      return true;
    }
    if (normalized === 'false' || normalized === '0' || normalized === 'no') {
      return false;
    }
  }

  throw new HttpError(400, 'Value must be a boolean');
}

export function normalizeGroupNames(value) {
  if (value === undefined || value === null) {
    return null;
  }

  if (!Array.isArray(value)) {
    throw new HttpError(400, 'group_names must be an array of strings');
  }

  const normalized = value
    .map((item) => String(item).trim())
    .filter(Boolean);

  return normalized.length ? normalized : null;
}

export function normalizeFormulation(value) {
  if (value === undefined || value === null) {
    return null;
  }

  if (!Array.isArray(value)) {
    throw new HttpError(400, 'formulation must be an array');
  }

  return value;
}

export function paginationFromQuery(searchParams, defaults = { limit: 25, maxLimit: 100 }) {
  const rawLimit = searchParams.get('limit');
  const rawCursor = searchParams.get('cursor');

  let limit = defaults.limit;
  if (rawLimit !== null) {
    const parsedLimit = Number(rawLimit);
    if (!Number.isInteger(parsedLimit) || parsedLimit <= 0) {
      throw new HttpError(400, 'limit must be a positive integer');
    }
    limit = Math.min(parsedLimit, defaults.maxLimit);
  }

  let cursor = null;
  if (rawCursor !== null) {
    const parsedCursor = Number(rawCursor);
    if (!Number.isInteger(parsedCursor) || parsedCursor <= 0) {
      throw new HttpError(400, 'cursor must be a positive integer');
    }
    cursor = parsedCursor;
  }

  return { limit, cursor };
}
