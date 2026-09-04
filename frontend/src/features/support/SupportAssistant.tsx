import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowRight, Bot, CalendarDays, CircleHelp, ScanSearch } from "lucide-react";
import { request } from "../../core/api";
import type { SupportMessage } from "../../core/types";

export type AssistantTurnResponse = {
  answer: string;
  intent: string;
  intentConfidence: number;
  escalated: boolean;
  conversationStatus: string;
  escalationReason?: string | null;
};

export default function SupportAssistant({
  token,
  messages,
  onUpdated,
}: {
  token: string;
  messages: SupportMessage[];
  onUpdated: (result: AssistantTurnResponse) => Promise<void>;
}) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const questionRef = useRef<HTMLTextAreaElement>(null);
  // Keep the human-support history in the same thread when a resolved request
  // returns to AI-first mode; the patient never has to reconstruct the context.
  const transcript = messages.filter(message => ["PATIENT", "AI", "SYSTEM", "RECEPTIONIST"].includes(message.senderRole));

  useEffect(() => {
    // Follow the outgoing message, typing state and incoming reply inside the
    // chat viewport so the patient never has to drag the scrollbar manually.
    const frame = window.requestAnimationFrame(() => {
      const list = messageListRef.current;
      if (!list) return;
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      list.scrollTo({ top: list.scrollHeight, behavior: reducedMotion ? "auto" : "smooth" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [transcript.length, pendingQuestion, busy]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (!value || busy) return;

    setQuestion("");
    setError("");
    setPendingQuestion(value);
    setBusy(true);
    try {
      // Appointment Service owns persistence, real availability and escalation,
      // so refresh or WebSocket reconnect cannot lose the support transcript.
      const result = await request<AssistantTurnResponse>("/appointments/support/assistant", token, {
        method: "POST",
        body: JSON.stringify({ question: value }),
      });
      await onUpdated(result);
      setPendingQuestion(null);
    } catch (reason) {
      setQuestion(value);
      setPendingQuestion(null);
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function useSuggestion(value: string) {
    setQuestion(value);
    window.requestAnimationFrame(() => questionRef.current?.focus());
  }

  return <div className="support-ai-shell">
    <div ref={messageListRef} className="support-messages support-ai-messages" role="log" aria-live="polite" aria-label="Nội dung trao đổi với trợ lý hỗ trợ">
      {transcript.length === 0 && <section className="support-ai-welcome" aria-labelledby="support-ai-welcome-title">
        <span className="support-ai-welcome-icon" aria-hidden="true"><Bot /></span>
        <div><h3 id="support-ai-welcome-title">Bạn cần hỗ trợ điều gì?</h3><p>Trợ lý Derm có thể hướng dẫn đặt lịch, kiểm tra giờ trống, giá khám và cách sử dụng kiểm tra da bằng AI.</p></div>
        <div className="support-ai-suggestions" aria-label="Câu hỏi gợi ý">
          <button type="button" onClick={() => useSuggestion("Tôi muốn đặt lịch khám")}><CalendarDays aria-hidden="true" />Tôi muốn đặt lịch</button>
          <button type="button" onClick={() => useSuggestion("Làm sao để đổi lịch khám?")}><CircleHelp aria-hidden="true" />Làm sao để đổi lịch?</button>
          <button type="button" onClick={() => useSuggestion("AI đánh giá da hoạt động thế nào?")}><ScanSearch aria-hidden="true" />AI đánh giá da hoạt động thế nào?</button>
        </div>
      </section>}
      {transcript.map(message => <article className={message.senderRole === "PATIENT" ? "mine" : message.senderRole === "SYSTEM" ? "system" : "theirs support-ai-message"} key={message.id}>
        <b>{message.senderRole === "PATIENT" ? "Bạn" : message.senderRole === "SYSTEM" ? "Hệ thống" : message.senderRole === "RECEPTIONIST" ? "Lễ tân Derm" : "Trợ lý Derm"}</b>
        <p>{message.body}</p>
        <small>{new Date(message.sentAt).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</small>
      </article>)}
      {pendingQuestion && <article className="mine support-ai-pending" aria-label="Tin nhan dang gui">
        <b>Bạn</b>
        <p>{pendingQuestion}</p>
        <small>Dang gui...</small>
      </article>}
      {busy && <article className="theirs support-ai-message support-ai-typing"><Bot aria-hidden="true" /><span>Đang kiểm tra dữ liệu và yêu cầu…</span></article>}
    </div>

    <form className="support-ai-form" onSubmit={send}>
      <label className="sr-only" htmlFor="support-ai-question">Nội dung cần hỗ trợ</label>
      <textarea ref={questionRef} id="support-ai-question" aria-keyshortcuts="Enter" title="Enter để gửi, Shift + Enter để xuống dòng" maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => {
        // Follow familiar chat behavior while keeping Shift+Enter available
        // for a deliberate line break and respecting Vietnamese IME input.
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
          event.preventDefault();
          event.currentTarget.form?.requestSubmit();
        }
      }} placeholder="Ví dụ: Lịch bác sĩ Bình ngày mai…" />
      <button type="submit" aria-label="Gửi câu hỏi cho trợ lý hỗ trợ" disabled={busy || !question.trim()}><ArrowRight aria-hidden="true" /></button>
    </form>
    {error && <small className="support-error" role="alert">{error}</small>}
  </div>;
}
