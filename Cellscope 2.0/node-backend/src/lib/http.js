import { HttpError } from './errors.js';

export function writeJson(res, status, payload, corsOrigin = '*') {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Access-Control-Allow-Origin': corsOrigin,
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(body);
}

export function writeNoContent(res, corsOrigin = '*') {
  res.writeHead(204, {
    'Access-Control-Allow-Origin': corsOrigin,
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end();
}

export async function readJsonBody(req, maxBytes = 5_000_000) {
  let buffer = '';
  for await (const chunk of req) {
    buffer += chunk;
    if (buffer.length > maxBytes) {
      throw new HttpError(413, 'Request body is too large');
    }
  }

  if (!buffer.trim()) {
    return {};
  }

  try {
    return JSON.parse(buffer);
  } catch {
    throw new HttpError(400, 'Invalid JSON payload');
  }
}

export function parseJsonText(value, fallback = null) {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  if (typeof value !== 'string') {
    return value;
  }

  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function toSafeInt(value, fieldName) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new HttpError(400, `Invalid ${fieldName}`);
  }
  return parsed;
}
