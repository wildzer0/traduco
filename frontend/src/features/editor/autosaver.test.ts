import { ApiError } from "../../lib/api";
import { Autosaver, type SaveStatus } from "./autosaver";

function setup(initial = "a", hash = "h0") {
  const statuses: SaveStatus[] = [];
  const saves: { content: string; hash: string }[] = [];
  let n = 0;
  let impl = async (_c: string, _h: string): Promise<{ hash: string }> => ({ hash: `h${++n}` });
  const saver = new Autosaver(
    { content: initial, hash },
    {
      save: (content, h) => {
        saves.push({ content, hash: h });
        return impl(content, h);
      },
      onStatus: (s) => statuses.push(s),
    },
  );
  return { saver, statuses, saves, setImpl: (f: typeof impl) => (impl = f) };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("Autosaver", () => {
  it("saves once, 1 s after the last change, with the latest text", async () => {
    const { saver, saves, statuses } = setup();
    saver.update("b");
    vi.advanceTimersByTime(900);
    saver.update("c");
    vi.advanceTimersByTime(900);
    expect(saves).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(200);
    expect(saves).toEqual([{ content: "c", hash: "h0" }]);
    expect(statuses).toEqual(["dirty", "dirty", "saving", "saved"]);
  });

  it("uses the hash returned by the previous save for the next one", async () => {
    const { saver, saves } = setup();
    saver.update("b");
    await vi.advanceTimersByTimeAsync(1000);
    saver.update("c");
    await vi.advanceTimersByTimeAsync(1000);
    expect(saves.map((s) => s.hash)).toEqual(["h0", "h1"]);
  });

  it("does not save when the text returns to the saved value", async () => {
    const { saver, saves, statuses } = setup();
    saver.update("b");
    saver.update("a");
    await vi.advanceTimersByTimeAsync(2000);
    expect(saves).toHaveLength(0);
    expect(statuses.at(-1)).toBe("saved");
  });

  it("writes a change made during a save right after it, never two at once", async () => {
    const { saver, saves, setImpl } = setup();
    let release: (v: { hash: string }) => void = () => {};
    setImpl(() => new Promise((r) => (release = r)));
    saver.update("b");
    await vi.advanceTimersByTimeAsync(1000);
    expect(saves).toHaveLength(1);
    saver.update("c");
    await vi.advanceTimersByTimeAsync(5000);
    expect(saves).toHaveLength(1); // still waiting for the first
    setImpl(async () => ({ hash: "h2" }));
    release({ hash: "h1" });
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(1000);
    expect(saves.map((s) => [s.content, s.hash])).toEqual([
      ["b", "h0"],
      ["c", "h1"],
    ]);
  });

  it("flush saves immediately", async () => {
    const { saver, saves } = setup();
    saver.update("b");
    await saver.flush();
    expect(saves).toEqual([{ content: "b", hash: "h0" }]);
    expect(saver.currentStatus).toBe("saved");
  });

  it("stops on conflict and resumes with keepMine using the disk hash", async () => {
    const { saver, saves, setImpl } = setup();
    setImpl(async () => {
      throw new ApiError(409, "conflict", "changed", { current_hash: "disk" });
    });
    saver.update("mine");
    await saver.flush();
    expect(saver.currentStatus).toBe("conflict");
    saver.update("mine2");
    await vi.advanceTimersByTimeAsync(3000);
    expect(saves).toHaveLength(1); // nothing is retried while in conflict
    setImpl(async () => ({ hash: "h9" }));
    await saver.keepMine("disk");
    expect(saves.at(-1)).toEqual({ content: "mine2", hash: "disk" });
    expect(saver.currentStatus).toBe("saved");
  });

  it("reset adopts the disk version and clears the conflict", async () => {
    const { saver, saves, setImpl } = setup();
    setImpl(async () => {
      throw new ApiError(409, "conflict", "x", { current_hash: "disk" });
    });
    saver.update("mine");
    await saver.flush();
    saver.reset("from disk", "disk");
    expect(saver.dirty).toBe(false);
    saver.update("from disk");
    await vi.advanceTimersByTimeAsync(2000);
    expect(saves).toHaveLength(1);
  });

  it("reports other errors and retries on the next change", async () => {
    const { saver, saves, setImpl } = setup();
    setImpl(async () => {
      throw new Error("network");
    });
    saver.update("b");
    await saver.flush();
    expect(saver.currentStatus).toBe("error");
    setImpl(async () => ({ hash: "h1" }));
    saver.update("bb");
    await vi.advanceTimersByTimeAsync(1000);
    expect(saves).toHaveLength(2);
    expect(saver.currentStatus).toBe("saved");
  });

  describe("normalisation", () => {
    function withNormalize(initial: string) {
      const saves: string[] = [];
      const saver = new Autosaver(
        { content: initial, hash: "h0" },
        {
          save: async (c) => {
            saves.push(c);
            return { hash: `h${saves.length}` };
          },
          onStatus: () => {},
          normalize: (t) => t.trim().replace(/[ \t]+/g, " "),
        },
      );
      return { saver, saves };
    }

    it("writes the normalised text but stays clean afterwards (no save loop)", async () => {
      const { saver, saves } = withNormalize("ciao");
      saver.update("ciao   mondo  ");
      await vi.advanceTimersByTimeAsync(1000);
      expect(saves).toEqual(["ciao mondo"]);
      expect(saver.dirty).toBe(false);
      await vi.advanceTimersByTimeAsync(10_000);
      expect(saves).toHaveLength(1);
    });

    it("skips the write when the edit normalises to what is already on disk", async () => {
      const { saver, saves } = withNormalize("ciao");
      saver.update("ciao   ");
      await vi.advanceTimersByTimeAsync(1000);
      expect(saves).toHaveLength(0);
      expect(saver.currentStatus).toBe("saved");
    });
  });

  describe("external changes", () => {
    it("ignores events that carry our own hash", async () => {
      const { saver } = setup();
      saver.update("b");
      await saver.flush();
      expect(saver.noteExternalChange(saver.knownHash)).toBe("ignore");
    });

    it("asks for a silent reload when there is nothing unsaved", () => {
      const { saver } = setup();
      expect(saver.noteExternalChange("other")).toBe("reload");
    });

    it("treats an edit the editor has not reported yet as unsaved (no lost keystrokes)", () => {
      const { saver } = setup();
      saver.touch();
      expect(saver.dirty).toBe(true);
      expect(saver.noteExternalChange("other")).toBe("conflict");
    });

    it("an edit report or a reset clears the pending flag", () => {
      const { saver } = setup();
      saver.touch();
      saver.update("a"); // same as saved: nothing to write
      expect(saver.dirty).toBe(false);
      saver.touch();
      saver.reset("x", "h9");
      expect(saver.dirty).toBe(false);
    });

    it("raises a conflict when the user has unsaved changes", () => {
      const { saver, saves } = setup();
      saver.update("typing");
      expect(saver.noteExternalChange("other")).toBe("conflict");
      expect(saver.currentStatus).toBe("conflict");
      vi.advanceTimersByTime(5000);
      expect(saves).toHaveLength(0);
    });
  });

  it("does nothing after dispose", async () => {
    const { saver, saves } = setup();
    saver.update("b");
    saver.dispose();
    saver.update("c");
    await vi.advanceTimersByTimeAsync(3000);
    expect(saves).toHaveLength(0);
  });
});
