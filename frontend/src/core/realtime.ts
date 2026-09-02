export type RealtimeEvent = { type: string } & Record<string, unknown>;
export type RealtimeConnectionState = "connecting" | "connected" | "reconnecting" | "closed";

type SocketLike = Pick<WebSocket, "close"> & {
  onopen: WebSocket["onopen"];
  onmessage: WebSocket["onmessage"];
  onclose: WebSocket["onclose"];
  onerror: WebSocket["onerror"];
};

type Options = {
  url?: string;
  path?: string;
  reconnectMs?: number;
  createSocket?: (url: string) => SocketLike;
  schedule?: (callback: () => void, delay: number) => number;
  cancel?: (id: number) => void;
  onConnectionChange?: (state: RealtimeConnectionState) => void;
};

export function subscribeRealtime(listener: (event: RealtimeEvent) => void, options: Options = {}) {
  const browserLocation = typeof location === "undefined" ? { protocol: "http:", host: "localhost" } : location;
  const protocol = browserLocation.protocol === "https:" ? "wss:" : "ws:";
  const path = options.path ?? "/api/v1/appointments/ws/slots";
  const url = options.url ?? `${protocol}//${browserLocation.host}${path}`;
  const createSocket = options.createSocket ?? (value => new WebSocket(value));
  const schedule = options.schedule ?? ((callback, delay) => globalThis.setTimeout(callback, delay) as unknown as number);
  const cancel = options.cancel ?? (id => globalThis.clearTimeout(id));
  const onConnectionChange = options.onConnectionChange ?? (() => undefined);
  const reconnectMs = options.reconnectMs ?? 2_000;
  let active = true;
  let socket: SocketLike | undefined;
  let retry: number | undefined;

  const connect = () => {
    if (!active) return;
    onConnectionChange(socket ? "reconnecting" : "connecting");
    const connected = createSocket(url);
    socket = connected;
    connected.onopen = () => onConnectionChange("connected");
    connected.onmessage = event => {
      try {
        const parsed = JSON.parse(event.data) as RealtimeEvent;
        listener(parsed);
      } catch {
        // Ignore malformed frames and keep the connection alive.
      }
    };
    connected.onerror = () => connected.close();
    connected.onclose = () => {
      if (active) {
        onConnectionChange("reconnecting");
        retry = schedule(connect, reconnectMs);
      }
    };
  };

  connect();
  return () => {
    active = false;
    if (retry !== undefined) cancel(retry);
    socket?.close();
    onConnectionChange("closed");
  };
}

let sharedAudioContext: AudioContext | null = null;

function getAudioContext() {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return null;
    if (!sharedAudioContext) {
      sharedAudioContext = new AudioCtx();
    }
    return sharedAudioContext;
  } catch {
    return null;
  }
}

export function enableChimeNotifications() {
  const context = getAudioContext();
  if (!context || context.state === "closed") return;
  if (context.state === "suspended") void context.resume().catch(() => undefined);
}

function renderChime(ctx: AudioContext) {
  try {
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(523.25, ctx.currentTime);
    gain1.gain.setValueAtTime(0.2, ctx.currentTime);
    gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(ctx.currentTime);
    osc1.stop(ctx.currentTime + 0.35);

    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.setValueAtTime(659.25, ctx.currentTime + 0.12);
    gain2.gain.setValueAtTime(0.25, ctx.currentTime + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.55);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(ctx.currentTime + 0.12);
    osc2.stop(ctx.currentTime + 0.55);
  } catch {
    // Audio is optional and must never interrupt realtime updates.
  }
}

export function playChimeNotification() {
  const context = getAudioContext();
  if (!context || context.state === "closed") return;
  if (context.state === "suspended") {
    void context.resume().then(() => renderChime(context)).catch(() => undefined);
    return;
  }
  renderChime(context);
}

type AccountStatusEvent = { type: "ACCOUNT_STATUS_CHANGED"; identityId: string; status: string };

/** A bearer-authenticated event stream used for private account state changes. */
export function subscribeAccountStatus(token: string, listener: (event: AccountStatusEvent) => void) {
  let active = true;
  let retry: ReturnType<typeof setTimeout> | undefined;
  let controller: AbortController | undefined;

  const connect = async () => {
    controller = new AbortController();
    try {
      const response = await fetch("/api/v1/auth/events/account-status", {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
      if (!response.ok || !response.body) throw new Error("ACCOUNT_EVENT_STREAM_UNAVAILABLE");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (active) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() || "";
        for (const frame of frames) {
          const data = frame.split(/\r?\n/).filter(line => line.startsWith("data:")).map(line => line.slice(5).trim()).join("");
          if (!data || data === "ready") continue;
          try {
            const event = JSON.parse(data) as AccountStatusEvent;
            if (event.type === "ACCOUNT_STATUS_CHANGED") listener(event);
          } catch {
            // Ignore malformed frames; the stream reconnects independently.
          }
        }
      }
    } catch {
      // Closing/reconnecting the stream is expected during network changes.
    } finally {
      if (active) retry = setTimeout(() => void connect(), 1_000);
    }
  };

  void connect();
  return () => {
    active = false;
    if (retry) clearTimeout(retry);
    controller?.abort();
  };
}