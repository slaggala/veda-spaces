/**
 * Client-side photo preparation (MTQ blocker closure §6.2): the long edge is scaled to at most 2048 px, the image is
 * re-encoded as JPEG quality 0.8 (which drops every EXIF block, GPS included, after the browser has applied the
 * orientation), and its SHA-256 is computed on the device for the server to verify.
 */
export const MAX_EDGE = 2048;
export const JPEG_QUALITY = 0.8;
export const MAX_BYTES = 15 * 1024 * 1024;

export interface PreparedPhoto { blob: Blob; sha256: string; width: number; height: number }

export function fitWithin(width: number, height: number, max = MAX_EDGE): { width: number; height: number } {
  const scale = Math.min(1, max / Math.max(width, height));
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

export async function sha256Hex(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function preparePhoto(file: Blob): Promise<PreparedPhoto> {
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  const { width, height } = fitWithin(bitmap.width, bitmap.height);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('This browser cannot prepare photos.');
  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('The photo could not be encoded.'))), 'image/jpeg', JPEG_QUALITY));
  if (blob.size > MAX_BYTES) throw new Error('The photo is larger than 15 MB even after resizing.');
  return { blob, sha256: await sha256Hex(blob), width, height };
}
