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
        listener(JSON.parse(event.data) as RealtimeEvent);
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
