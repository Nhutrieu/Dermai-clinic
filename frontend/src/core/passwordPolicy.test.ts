import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { authErrorMessage, isPasswordValid, passwordChecks, passwordValidationMessage } from "./passwordPolicy";

describe("password policy", () => {
  it("matches the backend 10 to 100 character contract", () => {
    expect(isPasswordValid("123456789")).toBe(false);
    expect(isPasswordValid("1234567890")).toBe(true);
    expect(isPasswordValid("a".repeat(100))).toBe(true);
    expect(isPasswordValid("a".repeat(101))).toBe(false);
  });

  it("shows the minimum requirement while retaining the full validation contract", () => {
    expect(passwordChecks("short").map(item => item.valid)).toEqual([false]);
    expect(passwordChecks("short").map(item => item.label)).toEqual([
      "Mật khẩu phải có ít nhất 10 ký tự.",
    ]);
    expect(passwordValidationMessage("short")).toBe("Mật khẩu phải có ít nhất 10 ký tự.");
  });

  it("maps backend auth errors to Vietnamese", () => {
    expect(authErrorMessage(new ApiError("EMAIL_EXISTS", 409, "EMAIL_EXISTS"))).toContain("đã được đăng ký");
    expect(authErrorMessage(new ApiError("Password must contain valid characters", 400))).not.toContain("Password");
    expect(authErrorMessage(new Error("Password must contain valid characters"))).toBe("Mật khẩu phải có từ 10 đến 100 ký tự.");
  });
});
