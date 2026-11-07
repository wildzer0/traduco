import { connectEvents, eventsUrl } from "./ws";

class FakeSocket {
  static all: FakeSocket[] = [];
  onmessage: ((m: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(readonly url: string) {
    FakeSocket.all.push(this);
  }
  close() {
    this.closed = true;
    this.onclose?.();
  }
  push(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
}

const create = (u: string) => new FakeSocket(u) as unknown as WebSocket;

beforeEach(() => {
  FakeSocket.all = [];
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

describe("eventsUrl", () => {
  it("uses ws/wss according to the page protocol and encodes the id", () => {
    expect(eventsUrl("a b", { protocol: "http:", host: "localhost:8000" })).toBe(
      "ws://localhost:8000/api/projects/a%20b/events",
    );
    expect(eventsUrl("x", { protocol: "https:", host: "h" })).toBe("wss://h/api/projects/x/events");
  });
});

describe("connectEvents", () => {
  it("calls onConnect on hello and onEvent for the rest", () => {
    const onEvent = vi.fn();
    const onConnect = vi.fn();
    connectEvents("p", { onEvent, onConnect, create });
    const s = FakeSocket.all[0] as FakeSocket;
    s.push({ type: "hello", project: "p" });
    s.push({ type: "file.changed", path: "capitoli/x.md", change: "modified", hash: "h" });
    expect(onConnect).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({
      type: "file.changed",
      path: "capitoli/x.md",
      change: "modified",
      hash: "h",
    });
  });

  it("reconnects with growing delays and resets the delay after a hello", () => {
    const onConnect = vi.fn();
    connectEvents("p", { onEvent: vi.fn(), onConnect, create });
    (FakeSocket.all[0] as FakeSocket).onclose?.();
    vi.advanceTimersByTime(999);
    expect(FakeSocket.all).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.all).toHaveLength(2);
    (FakeSocket.all[1] as FakeSocket).onclose?.();
    vi.advanceTimersByTime(2000);
    expect(FakeSocket.all).toHaveLength(3);
    (FakeSocket.all[2] as FakeSocket).push({ type: "hello" });
    expect(onConnect).toHaveBeenCalledTimes(1);
    (FakeSocket.all[2] as FakeSocket).onclose?.();
    vi.advanceTimersByTime(1000);
    expect(FakeSocket.all).toHaveLength(4);
  });

  it("does not reconnect after being closed", () => {
    const close = connectEvents("p", { onEvent: vi.fn(), create });
    close();
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.all).toHaveLength(1);
    expect((FakeSocket.all[0] as FakeSocket).closed).toBe(true);
  });
});
