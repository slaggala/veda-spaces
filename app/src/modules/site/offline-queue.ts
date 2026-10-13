import { api } from '../../core/api/client.js';

/**
 * The surveyor's offline queue (MTQ B1-T09/T10; blueprint §6.1 (4), §13.2).
 *
 * Every capture action becomes an operation stored locally (IndexedDB, or memory when the browser refuses storage)
 * before anything is sent. `flush` sends the queue in order through `/measurement-sets/{id}/sync` in batches of 50,
 * and handles each answer explicitly:
 *
 * - APPLIED, DUPLICATE: done, removed (a DUPLICATE is an earlier attempt that had landed);
 * - CONFLICT, CLAIMED: kept and shown with the server's version, never overwritten; the surveyor resolves it;
 * - FROZEN: the revision was submitted or returned meanwhile; kept with the draft that now holds the property;
 * - REJECTED: kept with the server's reasons until the surveyor fixes or discards it;
 * - network failure: kept untouched and retried later (no partial state on the device).
 *
 * Photos queue with their bytes; their metadata goes first in the batch, the bytes upload after it is accepted.
 */
export type OpType = 'space' | 'note' | 'release' | 'property_capture' | 'attachment';
export type OpState = 'PENDING' | 'CONFLICT' | 'CLAIMED' | 'FROZEN' | 'REJECTED' | 'UPLOADING';

export interface QueuedOp {
  op_id: string;
  set_id: string;
  seq: number;
  type: OpType;
  space_id: string | null;
  data: Record<string, unknown>;
  state: OpState;
  result?: Record<string, unknown>;
  label: string;
}

export interface SyncResult {
  op_id: string; status: string; code?: string; message?: string; version?: number; entity_id?: string;
  server?: Record<string, unknown>; conflicting_fields?: string[]; current_version?: number; current_draft_id?: string | null;
  upload?: { required: boolean; method?: string; url?: string; fields?: Record<string, string>; then?: string };
  errors?: Array<{ field: string; message: string }>;
}

const DB = 'veda-site';
const BATCH = 50;

interface Store {
  all(): Promise<QueuedOp[]>;
  put(op: QueuedOp): Promise<void>;
  remove(opId: string): Promise<void>;
  putBlob(key: string, blob: Blob): Promise<void>;
  getBlob(key: string): Promise<Blob | undefined>;
  removeBlob(key: string): Promise<void>;
}

export class MemoryStore implements Store {
  private ops = new Map<string, QueuedOp>();
  private blobs = new Map<string, Blob>();
  async all() { return [...this.ops.values()]; }
  async put(op: QueuedOp) { this.ops.set(op.op_id, op); }
  async remove(id: string) { this.ops.delete(id); }
  async putBlob(k: string, b: Blob) { this.blobs.set(k, b); }
  async getBlob(k: string) { return this.blobs.get(k); }
  async removeBlob(k: string) { this.blobs.delete(k); }
}

class IdbStore implements Store {
  private db: Promise<IDBDatabase>;
  constructor() {
    this.db = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore('ops', { keyPath: 'op_id' });
        req.result.createObjectStore('blobs');
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  private async tx<T>(store: string, mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    const db = await this.db;
    return new Promise((resolve, reject) => {
      const req = fn(db.transaction(store, mode).objectStore(store));
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  all() { return this.tx<QueuedOp[]>('ops', 'readonly', (s) => s.getAll() as IDBRequest<QueuedOp[]>); }
  async put(op: QueuedOp) { await this.tx('ops', 'readwrite', (s) => s.put(op)); }
  async remove(id: string) { await this.tx('ops', 'readwrite', (s) => s.delete(id)); }
  async putBlob(k: string, b: Blob) { await this.tx('blobs', 'readwrite', (s) => s.put(b, k)); }
  getBlob(k: string) { return this.tx<Blob | undefined>('blobs', 'readonly', (s) => s.get(k) as IDBRequest<Blob | undefined>); }
  async removeBlob(k: string) { await this.tx('blobs', 'readwrite', (s) => s.delete(k)); }
}

function openStore(): Store {
  try {
    if (typeof indexedDB !== 'undefined') return new IdbStore();
  } catch { /* storage refused (private mode): fall back to memory */ }
  return new MemoryStore();
}

export function newRef(prefix: string): string {
  return `${prefix}-${crypto.randomUUID().replace(/-/g, '').slice(0, 20)}`;
}

export class OfflineQueue extends EventTarget {
  private store: Store;
  private seq = Date.now();
  private flushing: Promise<SyncResult[]> | null = null;
  online = typeof navigator === 'undefined' ? true : navigator.onLine;

  constructor(store?: Store) {
    super();
    this.store = store ?? openStore();
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => { this.online = true; this.changed(); });
      window.addEventListener('offline', () => { this.online = false; this.changed(); });
    }
  }

  private changed() { this.dispatchEvent(new Event('change')); }

  async pending(setId: string): Promise<QueuedOp[]> {
    return (await this.store.all()).filter((o) => o.set_id === setId).sort((a, b) => a.seq - b.seq);
  }

  /** Queue one operation; a later write to the same space replaces an earlier one that has not been sent. */
  async enqueue(setId: string, type: OpType, data: Record<string, unknown>, opts: { spaceId?: string | null; label?: string } = {}): Promise<QueuedOp> {
    if (type === 'space' && opts.spaceId) {
      for (const o of await this.pending(setId)) {
        if (o.type === 'space' && o.space_id === opts.spaceId && o.state === 'PENDING') await this.store.remove(o.op_id);
      }
    }
    const op: QueuedOp = {
      op_id: newRef('op'), set_id: setId, seq: this.seq++, type, space_id: opts.spaceId ?? null, data,
      state: 'PENDING', label: opts.label ?? type,
    };
    await this.store.put(op);
    this.changed();
    return op;
  }

  async queuePhoto(setId: string, meta: Record<string, unknown>, blob: Blob, label = 'photo'): Promise<QueuedOp> {
    const op = await this.enqueue(setId, 'attachment', meta, { label });
    await this.store.putBlob(op.op_id, blob);
    return op;
  }

  async discard(opId: string): Promise<void> {
    await this.store.remove(opId);
    await this.store.removeBlob(opId);
    this.changed();
  }

  /** Replace a conflicted space write with the surveyor's choice, rebased on the server's current version. */
  async resolve(op: QueuedOp, keep: 'MINE' | 'SERVER'): Promise<void> {
    if (keep === 'SERVER') return this.discard(op.op_id);
    const current = (op.result?.current_version as number | undefined) ?? undefined;
    await this.store.put({ ...op, state: 'PENDING', data: { ...op.data, base_version: current, take_over: op.state === 'CLAIMED' ? true : op.data.take_over }, result: undefined });
    this.changed();
  }

  /** Send everything pending for a set; safe to call repeatedly (one flush at a time). */
  flush(setId: string): Promise<SyncResult[]> {
    if (!this.flushing) {
      this.flushing = this.doFlush(setId).finally(() => { this.flushing = null; this.changed(); });
    }
    return this.flushing;
  }

  private async doFlush(setId: string): Promise<SyncResult[]> {
    const out: SyncResult[] = [];
    const queue = (await this.pending(setId)).filter((o) => o.state === 'PENDING');
    for (let i = 0; i < queue.length; i += BATCH) {
      const chunk = queue.slice(i, i + BATCH);
      let results: SyncResult[];
      try {
        const r = await api.request<{ results: SyncResult[] }>(`/api/v1/measurement-sets/${setId}/sync`, {
          method: 'POST',
          body: { batch_id: newRef('batch'), operations: chunk.map((o) => ({ op_id: o.op_id, type: o.type, space_id: o.space_id, data: o.data })) },
        });
        results = r.data.results;
      } catch {
        this.online = false;
        return out; // keep everything; try again when the connection is back
      }
      for (const res of results) {
        const op = chunk.find((o) => o.op_id === res.op_id);
        if (!op) continue;
        out.push(res);
        if (res.status === 'APPLIED' || res.status === 'DUPLICATE') {
          if (op.type === 'attachment' && res.upload?.required && res.entity_id) {
            await this.store.put({ ...op, state: 'UPLOADING', result: res as unknown as Record<string, unknown> });
            await this.upload(op, res);
          } else {
            await this.store.remove(op.op_id);
          }
        } else {
          await this.store.put({ ...op, state: res.status as OpState, result: res as unknown as Record<string, unknown> });
        }
      }
    }
    return out;
  }

  /**
   * Upload a queued photo's bytes, then ask the server to verify, scan and re-encode them. The completion step is the
   * proof of arrival (length, SHA-256 and type checked by the server); until it succeeds the photo stays UPLOADING.
   */
  private async upload(op: QueuedOp, res: SyncResult, retry = false): Promise<void> {
    const blob = await this.store.getBlob(op.op_id);
    if (!blob || !res.entity_id) return;
    try {
      // A retry asks for fresh instructions: a pre-signed POST lives five minutes, and the server may already have it.
      const upload = retry
        ? (await api.request<{ upload?: SyncResult['upload'] }>(`/api/v1/attachments/${res.entity_id}`)).data.upload
        : res.upload;
      if (upload?.required) await sendBytes(res.entity_id, blob, upload);
      await api.request(`/api/v1/attachments/${res.entity_id}/complete`, { method: 'POST' });
      await this.store.remove(op.op_id);
      await this.store.removeBlob(op.op_id);
    } catch {
      await this.store.put({ ...op, state: 'UPLOADING', result: res as unknown as Record<string, unknown> });
    }
  }

  /** Retry photo uploads interrupted by a lost connection (their metadata is already on the server). */
  async resumeUploads(setId: string): Promise<void> {
    for (const op of (await this.pending(setId)).filter((o) => o.state === 'UPLOADING')) {
      await this.upload(op, op.result as unknown as SyncResult, true);
    }
    this.changed();
  }
}

/**
 * Send bytes the way the server asked. S3 (staging): a pre-signed POST straight to the private bucket. The bucket has
 * no CORS (refused by the infrastructure plan guard), so the multipart POST is sent as a simple request whose answer
 * the browser does not expose (`no-cors`); the server's completion step, not this answer, decides whether it arrived.
 * Local development: the local-only PUT through the API.
 */
export async function sendBytes(attachmentId: string, blob: Blob, upload: NonNullable<SyncResult['upload']>,
  onProgress?: (fraction: number) => void, fetchImpl: typeof fetch = (...a) => fetch(...a)): Promise<void> {
  if (!upload.required) return;
  if (upload.method === 'POST' && upload.url) {
    const form = new FormData();
    for (const [k, v] of Object.entries(upload.fields ?? {})) form.append(k, v);
    form.append('file', blob); // S3 requires the file to be the last field
    await fetchImpl(upload.url, { method: 'POST', body: form, mode: 'no-cors', credentials: 'omit', referrerPolicy: 'no-referrer' });
    onProgress?.(1);
    return;
  }
  const base64 = await blobToBase64(blob);
  await api.request(`/api/v1/attachments/${attachmentId}/content`, { method: 'PUT', body: { data_base64: base64 } });
  onProgress?.(1);
}

async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

export const queue = new OfflineQueue();
