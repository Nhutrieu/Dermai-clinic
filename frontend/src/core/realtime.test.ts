import { afterEach, describe, expect, it, vi } from "vitest";
import { subscribeRealtime } from "./realtime";

class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: WebSocket["onopen"] = null;
  onmessage: WebSocket["onmessage"] = null;
  onclose: WebSocket["onclose"] = null;
  onerror: WebSocket["onerror"] = null;
  constructor(public url: string) { FakeSocket.instances.push(this); }
  close() { this.onclose?.call(this as unknown as WebSocket, {} as CloseEvent); }
  open() { this.onopen?.call(this as unknown as WebSocket, {} as Event); }
  message(data: string) { this.onmessage?.call(this as unknown as WebSocket, { data } as MessageEvent<string>); }
}

describe("subscribeRealtime", () => {
  afterEach(() => { FakeSocket.instances = []; vi.useRealTimers(); });

  it("delivers valid events and ignores malformed frames", () => {
    const listener = vi.fn();
    const stop = subscribeRealtime(listener, { createSocket: url => new FakeSocket(url), schedule: () => 1, cancel: () => undefined });
    FakeSocket.instances[0].message('{"type":"SLOTS_CHANGED"}');
    FakeSocket.instances[0].message("not-json");
    expect(listener).toHaveBeenCalledOnce();
    expect(listener).toHaveBeenCalledWith({ type: "SLOTS_CHANGED" });
    stop();
  });

  it("reconnects after a dropped connection and stops cleanly", () => {
    vi.useFakeTimers();
    const stop = subscribeRealtime(vi.fn(), { createSocket: url => new FakeSocket(url), reconnectMs: 2_000 });
    FakeSocket.instances[0].close();
    vi.advanceTimersByTime(1_999);
    expect(FakeSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.instances).toHaveLength(2);
    stop();
    vi.runAllTimers();
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("connects to a feature-specific websocket path", () => {
    const stop = subscribeRealtime(vi.fn(), {
      path: "/api/v1/doctors/ws/profile",
      createSocket: url => new FakeSocket(url),
    });
    expect(FakeSocket.instances[0].url).toBe("ws://localhost/api/v1/doctors/ws/profile");
    stop();
  });

  it("reports connection changes without changing event delivery", () => {
    const states: string[] = [];
    const stop = subscribeRealtime(vi.fn(), {
      createSocket: url => new FakeSocket(url),
      schedule: () => 1,
      cancel: () => undefined,
      onConnectionChange: state => states.push(state),
    });
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].close();
    stop();
    expect(states).toEqual(["connecting", "connected", "reconnecting", "closed"]);
  });
});
