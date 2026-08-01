import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "a[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

type AccessibleDialogProps = {
  title: string;
  titleId: string;
  descriptionId?: string;
  children: ReactNode;
  footer?: ReactNode;
  icon?: ReactNode;
  role?: "dialog" | "alertdialog";
  tone?: "neutral" | "warning" | "danger" | "success";
  className?: string;
  backdropClassName?: string;
  closeLabel?: string;
  closeOnBackdrop?: boolean;
  onClose: () => void;
};

/**
 * Primitive dialog dùng chung cho booking bệnh nhân và lễ tân.
 * Component quản lý Escape, focus trap, khóa cuộn nền và trả focus khi đóng.
 */
export default function AccessibleDialog({
  title,
  titleId,
  descriptionId,
  children,
  footer,
  icon,
  role = "dialog",
  tone = "neutral",
  className = "",
  backdropClassName = "",
  closeLabel = "Đóng hộp thoại",
  closeOnBackdrop = true,
  onClose,
}: AccessibleDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const dialog = dialogRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const initialFocus = dialog?.querySelector<HTMLElement>("[data-dialog-initial-focus]")
      || dialog?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
      || dialog;
    initialFocus?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;

      const items = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (!items.length) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus();
    };
  }, []);

  const content = (
    <div
      className={["booking-dialog-backdrop", backdropClassName].filter(Boolean).join(" ")}
      role="presentation"
      onMouseDown={event => {
        if (closeOnBackdrop && event.target === event.currentTarget) onClose();
      }}
    >
      <section
        ref={dialogRef}
        className={[
          "booking-dialog",
          `booking-dialog-${tone}`,
          className,
        ].filter(Boolean).join(" ")}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
      >
        <button
          type="button"
          className="booking-dialog-close"
          aria-label={closeLabel}
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </button>
        {icon && <span className="booking-dialog-icon" aria-hidden="true">{icon}</span>}
        <h2 id={titleId}>{title}</h2>
        <div id={descriptionId} className="booking-dialog-copy">{children}</div>
        {footer && <div className="booking-dialog-actions">{footer}</div>}
      </section>
    </div>
  );

  // Giữ component render được trong test SSR mà không cần mock document.
  return typeof document === "undefined" ? content : createPortal(content, document.body);
}
