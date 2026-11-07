import { ApiError } from "../../lib/api";

export type SaveStatus = "saved" | "dirty" | "saving" | "error" | "conflict";

export interface AutosaverOptions {
  /** Persist ``content`` if the file still has ``hash``; resolves to the new hash. */
  save: (content: string, hash: string) => Promise<{ hash: string }>;
  onStatus: (status: SaveStatus) => void;
  /** Quiet period before saving (RF-15: 1 s). */
  delay?: number;
  /** Applied to the text just before writing (canonical form, RF-10c); the editor view is untouched. */
  normalize?: (text: string) => string;
}

/**
 * Debounced, single-flight saver with optimistic concurrency (RF-15, docs/03-ui.md).
 * - changes are coalesced: only the latest text is written after ``delay`` ms of silence;
 * - a change made while a save is running is written right after it;
 * - a 409 from the server stops saving until the user picks "reload" or "keep mine".
 */
export class Autosaver {
  private hash: string;
  private saved: string; // last editor text that is persisted (raw, as the editor shows it)
  private disk: string; // what is on disk
  private latest: string;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private inFlight: Promise<void> | null = null;
  private conflict = false;
  private disposed = false;
  currentStatus: SaveStatus = "saved";
  /** Hash of the newer disk version that caused the conflict, when known. */
  conflictHash: string | null = null;
  /** Hash of the disk version this saver last saw or wrote. */
  get knownHash(): string {
    return this.hash;
  }

  constructor(
    initial: { content: string; hash: string },
    private readonly opts: AutosaverOptions,
  ) {
    this.hash = initial.hash;
    this.saved = initial.content;
    this.disk = initial.content;
    this.latest = initial.content;
  }

  get dirty(): boolean {
    return this.latest !== this.saved;
  }

  private status(s: SaveStatus) {
    this.currentStatus = s;
    this.opts.onStatus(s);
  }

  /** The editor produced new text. */
  update(content: string): void {
    if (this.disposed) return;
    this.latest = content;
    if (this.conflict) return;
    if (!this.dirty) {
      clearTimeout(this.timer);
      if (!this.inFlight) this.status("saved");
      return;
    }
    this.status("dirty");
    clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.flush(), this.opts.delay ?? 1000);
  }

  /** Save now (used on blur, section change and page unload). Resolves when nothing is pending. */
  async flush(): Promise<void> {
    clearTimeout(this.timer);
    if (this.inFlight) {
      await this.inFlight;
      if (this.dirty && !this.conflict && this.currentStatus !== "error") return this.flush();
      return;
    }
    if (!this.dirty || this.conflict) return;
    const raw = this.latest;
    const content = this.opts.normalize ? this.opts.normalize(raw) : raw;
    if (content === this.disk) {
      this.saved = raw; // edits that normalise to what is already on disk need no write
      this.status("saved");
      return;
    }
    this.status("saving");
    this.inFlight = this.opts
      .save(content, this.hash)
      .then(({ hash }) => {
        this.hash = hash;
        this.disk = content;
        this.saved = raw;
        this.status(this.dirty ? "dirty" : "saved");
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.code === "conflict") {
          this.conflict = true;
          const current = e.details.current_hash;
          this.conflictHash = typeof current === "string" ? current : null;
          this.status("conflict");
        } else {
          this.status("error");
          // retry later: the text is still dirty, the next change or flush will try again
        }
      })
      .finally(() => {
        this.inFlight = null;
      });
    await this.inFlight;
    if (this.dirty && !this.conflict && this.currentStatus === "dirty") await this.flush();
  }

  /** The file changed on disk and the user keeps their text: adopt the disk hash and save over it. */
  keepMine(diskHash: string): Promise<void> {
    this.hash = diskHash;
    this.conflict = false;
    this.conflictHash = null;
    return this.flush();
  }

  /** The disk version replaces local text (after "reload"). */
  reset(content: string, hash: string): void {
    clearTimeout(this.timer);
    this.hash = hash;
    this.saved = content;
    this.disk = content;
    this.latest = content;
    this.conflict = false;
    this.conflictHash = null;
    this.status("saved");
  }

  /** Tell the saver that the disk changed under it (WebSocket event). */
  noteExternalChange(diskHash: string): "ignore" | "reload" | "conflict" {
    if (diskHash === this.hash) return "ignore"; // our own write
    if (!this.dirty && !this.inFlight) return "reload";
    this.conflict = true;
    this.conflictHash = diskHash;
    clearTimeout(this.timer);
    this.status("conflict");
    return "conflict";
  }

  dispose(): void {
    this.disposed = true;
    clearTimeout(this.timer);
  }
}
