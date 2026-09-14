const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

// Session-memory cache: retain the original audio, without re-encoding it.
// Bound memory and share pending requests across buttons for identical speech.
const speechCache = new Map<string, Blob>();
const pendingSpeech = new Map<string, Promise<Blob>>();
let speechCacheBytes = 0;
const MAX_SPEECH_CACHE_BYTES = 20 * 1024 * 1024;
let speechOwner: string | null = null;

export async function getSpeechAudio(token: string | null, text: string, language: string): Promise<Blob> {
  if (!token) throw new Error('Please sign in to listen.');
  if (speechOwner !== token) {
    speechCache.clear();
    speechCacheBytes = 0;
    pendingSpeech.clear();
    speechOwner = token;
  }
  const key = JSON.stringify([text, language]);
  const cached = speechCache.get(key);
  if (cached) {
    speechCache.delete(key);
    speechCache.set(key, cached);
    return cached;
  }
  const pending = pendingSpeech.get(key);
  if (pending) return pending;
  const request = (async () => {
    const res = await fetch(`${API_BASE}/tts/synthesize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text, language }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const detail = String(data.detail || `TTS error (${res.status})`);
      if (/quota.*exceeded|exceeded.*quota/i.test(detail)) {
        throw new Error('Speech quota is exhausted. Previously generated audio can still play. ' +
          (detail.match(/Try again in [\d:]+/i)?.[0] || 'Please try again after the quota resets.'));
      }
      throw new Error(detail);
    }
    const blob = await res.blob();
    if (!blob.size) throw new Error('Speech service returned empty audio.');
    if (speechOwner === token && blob.size <= MAX_SPEECH_CACHE_BYTES) {
      while (speechCacheBytes + blob.size > MAX_SPEECH_CACHE_BYTES || speechCache.size >= 20) {
        const oldest = speechCache.keys().next().value;
        if (oldest === undefined) break;
        speechCacheBytes -= speechCache.get(oldest)!.size;
        speechCache.delete(oldest);
      }
      speechCache.set(key, blob);
      speechCacheBytes += blob.size;
    }
    return blob;
  })();
  pendingSpeech.set(key, request);
  try { return await request; }
  finally { if (pendingSpeech.get(key) === request) pendingSpeech.delete(key); }
}

