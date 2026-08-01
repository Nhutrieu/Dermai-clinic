import { describe, expect, it } from "vitest";
import { ApiError } from "../../core/api";
import { technicalAnalysisError, validatePhoto } from "./PatientAiScreen";

function photo(size: number, type: string) {
  return { size, type } as File;
}

describe("patient AI photo validation", () => {
  it("accepts a supported image within the real backend limit", () => {
    expect(validatePhoto(photo(2 * 1024 * 1024, "image/jpeg"))).toBe("");
  });

  it("explains an unsupported file type", () => {
    expect(validatePhoto(photo(500_000, "image/gif"))).toContain("JPEG, PNG hoặc WebP");
  });

  it("explains a file larger than 10 MB", () => {
    expect(validatePhoto(photo(10 * 1024 * 1024 + 1, "image/png"))).toContain("10 MB");
  });
});

describe("patient AI technical error wording", () => {
  it("uses a calm message when the model service is unavailable", () => {
    const error = new ApiError("HTTP 503", 503);
    expect(technicalAnalysisError(error, "analyzing")).toContain("tạm thời chưa sẵn sàng");
  });

  it("distinguishes a failure while saving the completed analysis", () => {
    const error = new ApiError("HTTP 500", 500);
    expect(technicalAnalysisError(error, "saving")).toContain("chưa thể hoàn tất việc lưu kết quả");
  });
});
