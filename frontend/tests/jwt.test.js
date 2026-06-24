// tests/jwt.test.js
import { describe, it, expect } from "vitest";
import { decodeJwt, isExpired } from "@/lib/jwt";

describe("decodeJwt", () => {
  it("returns null for undefined", () => {
    expect(decodeJwt(undefined)).toBeNull();
  });

  it("returns null for null", () => {
    expect(decodeJwt(null)).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(decodeJwt("")).toBeNull();
  });

  it("returns null for a non-JWT string", () => {
    expect(decodeJwt("not-a-jwt")).toBeNull();
  });

  it("returns null for a string with only one part", () => {
    expect(decodeJwt("onlyonepart")).toBeNull();
  });

  it("decodes a valid JWT payload", () => {
    // header.payload.signature — payload is base64url-encoded JSON
    const payload = Buffer.from(
      JSON.stringify({ sub: "123", exp: 9999999999 }),
    ).toString("base64url");
    const token = `header.${payload}.signature`;
    const decoded = decodeJwt(token);
    expect(decoded).toEqual({ sub: "123", exp: 9999999999 });
  });
});

describe("isExpired", () => {
  it("returns true for undefined", () => {
    expect(isExpired(undefined)).toBe(true);
  });

  it("returns true for null", () => {
    expect(isExpired(null)).toBe(true);
  });

  it("returns true for empty string", () => {
    expect(isExpired("")).toBe(true);
  });

  it("returns true for a malformed token", () => {
    expect(isExpired("garbage")).toBe(true);
  });

  it("returns true for a token with no exp claim", () => {
    const payload = Buffer.from(JSON.stringify({ sub: "123" })).toString(
      "base64url",
    );
    const token = `h.${payload}.s`;
    expect(isExpired(token)).toBe(true);
  });

  it("returns true for a token that expired in the past", () => {
    const payload = Buffer.from(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) - 100 }),
    ).toString("base64url");
    const token = `h.${payload}.s`;
    expect(isExpired(token)).toBe(true);
  });

  it("returns false for a token that expires in the future", () => {
    const payload = Buffer.from(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }),
    ).toString("base64url");
    const token = `h.${payload}.s`;
    expect(isExpired(token)).toBe(false);
  });

  it("returns true for a token expiring within the skew window", () => {
    // exp is 5 seconds in the future, default skew is 10 → expired
    const payload = Buffer.from(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 5 }),
    ).toString("base64url");
    const token = `h.${payload}.s`;
    expect(isExpired(token, 10)).toBe(true);
  });

  it("returns false when skew is large enough to cover the remaining time", () => {
    // exp is 60 seconds in the future, skew is 30 → 60 > now+30 → not expired
    const payload = Buffer.from(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 60 }),
    ).toString("base64url");
    const token = `h.${payload}.s`;
    expect(isExpired(token, 30)).toBe(false);
  });
});