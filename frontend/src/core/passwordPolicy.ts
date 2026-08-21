import { ApiError } from "./api";

export const PASSWORD_MIN_LENGTH = 10;
export const PASSWORD_MAX_LENGTH = 100;

export type PasswordCheck = {
  id: "minimum";
  label: string;
  valid: boolean;
};

/**
 * Đồng bộ đúng contract @Size(min=10,max=100) của auth-service.
 * Không thêm quy tắc chữ hoa, số hoặc ký tự đặc biệt khi backend không yêu cầu.
 */
export function passwordChecks(password: string): PasswordCheck[] {
  return [
    { id: "minimum", label: `Mật khẩu phải có ít nhất ${PASSWORD_MIN_LENGTH} ký tự.`, valid: password.length >= PASSWORD_MIN_LENGTH },
  ];
}

export function isPasswordValid(password: string) {
  return password.length >= PASSWORD_MIN_LENGTH && password.length <= PASSWORD_MAX_LENGTH;
}

export function passwordValidationMessage(password: string) {
  if (!password) return "Vui lòng nhập mật khẩu.";
  if (password.length < PASSWORD_MIN_LENGTH) return `Mật khẩu phải có ít nhất ${PASSWORD_MIN_LENGTH} ký tự.`;
  if (password.length > PASSWORD_MAX_LENGTH) return `Mật khẩu không được vượt quá ${PASSWORD_MAX_LENGTH} ký tự.`;
  return "";
}

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  EMAIL_EXISTS: "Email này đã được đăng ký. Vui lòng đăng nhập hoặc dùng email khác.",
  BAD_CREDENTIALS: "Email hoặc mật khẩu không đúng.",
  EMAIL_NOT_VERIFIED: "Email chưa được xác minh. Vui lòng nhập mã OTP đã gửi.",
  INVALID_OTP: "Mã OTP không đúng hoặc đã hết hạn.",
  OTP_COOLDOWN: "Bạn vừa yêu cầu mã mới. Vui lòng chờ trước khi gửi lại.",
  ACCOUNT_BLOCKED: "Tài khoản đã bị khóa. Vui lòng liên hệ phòng khám.",
  INVALID_REFRESH: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
  GOOGLE_PATIENT_ONLY: "Đăng nhập Google chỉ áp dụng cho tài khoản bệnh nhân.",
  GOOGLE_ACCOUNT_MISMATCH: "Email này đã liên kết với một tài khoản Google khác.",
  GOOGLE_LINK_REQUIRES_PASSWORD: "Vui lòng đăng nhập bằng mật khẩu để liên kết tài khoản Google.",
  DISPLAY_NAME_REQUIRED: "Vui lòng nhập họ tên nhân viên.",
  SESSION_EXPIRED: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
};

export function authErrorMessage(value: unknown) {
  if (value instanceof ApiError) {
    if (value.code && AUTH_ERROR_MESSAGES[value.code]) return AUTH_ERROR_MESSAGES[value.code];
    if (AUTH_ERROR_MESSAGES[value.message]) return AUTH_ERROR_MESSAGES[value.message];
    if (value.status === 400 && /size|password|mật khẩu/i.test(value.message)) {
      return `Mật khẩu phải có từ ${PASSWORD_MIN_LENGTH} đến ${PASSWORD_MAX_LENGTH} ký tự.`;
    }
    if (/[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]/i.test(value.message)) {
      return value.message;
    }
    if (value.status >= 500) return "Dịch vụ tài khoản đang bận. Vui lòng thử lại sau.";
    if (value.status === 401) return "Email hoặc mật khẩu không đúng.";
    if (value.status === 403) return "Bạn không có quyền thực hiện thao tác này.";
    if (value.status === 409) return "Thông tin này đã được sử dụng hoặc vừa được thay đổi.";
    if (value.status === 429) return "Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.";
    return "Thông tin chưa hợp lệ. Vui lòng kiểm tra và thử lại.";
  }
  const message = value instanceof Error ? value.message : String(value || "");
  if (AUTH_ERROR_MESSAGES[message]) return AUTH_ERROR_MESSAGES[message];
  if (/password|passcode|credential|must contain|characters?|length|size/i.test(message)) {
    return `Mật khẩu phải có từ ${PASSWORD_MIN_LENGTH} đến ${PASSWORD_MAX_LENGTH} ký tự.`;
  }
  if (/[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]/i.test(message)) {
    return message;
  }
  return "Không thể xử lý yêu cầu. Vui lòng thử lại.";
}
