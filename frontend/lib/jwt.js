// lib/jwt.js
// Decode JWT `exp` without verifying — we never verify in Next.js (Django does that).

/** Decode a JWT payload without verifying the signature. Returns null on garbage. */
export function decodeJwt(token) {
  try {
    const [, payload] = token.split(".");
    const json = Buffer.from(payload, "base64url").toString("utf8");
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** True if the token is missing, malformed, or expires within `skewSeconds`. */
export function isExpired(token, skewSeconds = 10) {
  const payload = decodeJwt(token);
  if (!payload?.exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return payload.exp <= now + skewSeconds;
}