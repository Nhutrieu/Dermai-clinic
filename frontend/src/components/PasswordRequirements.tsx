import { Check, Circle } from "lucide-react";
import { passwordChecks } from "../core/passwordPolicy";

export default function PasswordRequirements({ password, id }: { password: string; id?: string }) {
  return (
    <span id={id} className="password-requirements" aria-live="polite">
      <span className="password-requirements-list" role="list" aria-label="Yêu cầu mật khẩu">
        {passwordChecks(password).map(item => (
          <span key={item.id} role="listitem" className={item.valid ? "is-valid" : ""}>
            {item.valid ? <Check aria-hidden="true" /> : <Circle aria-hidden="true" />}
            <span>{item.label}</span>
          </span>
        ))}
      </span>
    </span>
  );
}
