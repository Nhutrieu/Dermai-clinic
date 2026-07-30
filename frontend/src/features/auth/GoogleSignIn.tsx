import { useEffect, useRef, useState } from "react";
import { request } from "../../core/api";
import type { Tokens } from "../../core/types";

type GoogleConfig = { enabled: boolean; clientId: string };
export type GoogleLoginResult = Tokens & { newAccount: boolean; email: string; fullName: string };

type GoogleCredentialResponse = { credential: string; select_by: string };
type GoogleAccounts = {
  id: {
    initialize: (config: { client_id: string; callback: (response: GoogleCredentialResponse) => void; ux_mode?: "popup" }) => void;
    renderButton: (element: HTMLElement, options: Record<string, string | number>) => void;
  };
};

declare global {
  interface Window { google?: { accounts: GoogleAccounts } }
}

let googleScriptPromise: Promise<void> | null = null;

function loadGoogleScript() {
  if (window.google?.accounts) return Promise.resolve();
  if (googleScriptPromise) return googleScriptPromise;
  googleScriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-dermai-google="true"]');
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Không tải được Google Identity Services.")), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client?hl=vi";
    script.async = true;
    script.dataset.dermaiGoogle = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Không tải được Google Identity Services."));
    document.head.appendChild(script);
  });
  return googleScriptPromise;
}

export default function GoogleSignIn({ onAuthenticated }: { onAuthenticated: (result: GoogleLoginResult) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const callback = useRef(onAuthenticated);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { callback.current = onAuthenticated; }, [onAuthenticated]);

  useEffect(() => {
    let active = true;
    request<GoogleConfig>("/auth/google/config")
      .then(async config => {
        if (!active) return;
        setConfigured(config.enabled);
        if (!config.enabled || !host.current) return;
        await loadGoogleScript();
        if (!active || !host.current || !window.google) return;
        // Google trả ID token về callback; backend vẫn là nơi bắt buộc xác minh chữ ký và audience.
        window.google.accounts.id.initialize({
          client_id: config.clientId,
          ux_mode: "popup",
          callback: async response => {
            setError("");
            try {
              const result = await request<GoogleLoginResult>("/auth/google", undefined, {
                method: "POST",
                body: JSON.stringify({ credential: response.credential }),
              });
              callback.current(result);
            } catch (value) {
              setError((value as Error).message);
            }
          },
        });
        host.current.replaceChildren();
        window.google.accounts.id.renderButton(host.current, {
          type: "standard", theme: "outline", size: "large", text: "continue_with",
          shape: "rectangular", logo_alignment: "left", locale: "vi",
          width: Math.min(360, Math.max(240, host.current.clientWidth)),
        });
      })
      .catch(value => { if (active) setError((value as Error).message); });
    return () => { active = false; };
  }, []);

  return <div className="google-auth">
    <div className="auth-divider"><span>hoặc</span></div>
    {configured === false
      ? <button type="button" className="google-disabled" disabled>Đăng nhập với Google chưa được cấu hình</button>
      : <div ref={host} className="google-button-host" aria-busy={configured === null} />}
    {error && <div className="google-auth-error">{error}</div>}
  </div>;
}
