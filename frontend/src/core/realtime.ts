export type RealtimeEvent = { type: string } & Record<string, unknown>;

type SocketLike = Pick<WebSocket, "close"> & {
  onmessage: WebSocket["onmessage"];
  onclose: WebSocket["onclose"];
  onerror: WebSocket["onerror"];
};

type Options = {
  url?: string;
  reconnectMs?: number;
  createSocket?: (url: string) => SocketLike;
  schedule?: (callback: () => void, delay: number) => number;
  cancel?: (id: number) => void;
};

export function subscribeRealtime(listener: (event: RealtimeEvent) => void, options: Options = {}) {
  const browserLocation = typeof location === "undefined" ? { protocol: "http:", host: "localhost" } : location;
  const protocol = browserLocation.protocol === "https:" ? "wss:" : "ws:";
  const url = options.url ?? `${protocol}//${browserLocation.host}/api/v1/appointments/ws/slots`;
  const createSocket = options.createSocket ?? (value => new WebSocket(value));
  const schedule = options.schedule ?? ((callback, delay) => globalThis.setTimeout(callback, delay) as unknown as number);
  const cancel = options.cancel ?? (id => globalThis.clearTimeout(id));
  const reconnectMs = options.reconnectMs ?? 2_000;
  let active = true;
  let socket: SocketLike | undefined;
  let retry: number | undefined;

  const connect = () => {
    if (!active) return;
    const connected = createSocket(url);
    socket = connected;
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
      if (active) retry = schedule(connect, reconnectMs);
    };
  };

  connect();
  return () => {
    active = false;
    if (retry !== undefined) cancel(retry);
    socket?.close();
  };
}

let sharedAudioContext: AudioContext | null = null;

export function playChimeNotification() {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    if (!sharedAudioContext) {
      sharedAudioContext = new AudioCtx();
    }
    if (sharedAudioContext.state === "suspended") {
      sharedAudioContext.resume().catch(() => {});
    }

    const ctx = sharedAudioContext;
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
    // Ignore audio restriction
  }
}
