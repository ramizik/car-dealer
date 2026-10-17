// Mic capture for the seller's answer. Browser records webm/opus; we decode and re-encode as 16 kHz mono WAV,
// which is what Parakeet takes. Needs a secure context: localhost is fine, plain http on another host is not.

export type Recording = { stop: () => Promise<Blob> };

export async function startRecording(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const rec = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec.start();
  return {
    stop: () =>
      new Promise<Blob>((resolve, reject) => {
        rec.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          try {
            resolve(await toWav16k(new Blob(chunks, { type: rec.mimeType })));
          } catch (e) {
            reject(e);
          }
        };
        rec.stop();
      }),
  };
}

async function toWav16k(blob: Blob): Promise<Blob> {
  const ctx = new AudioContext({ sampleRate: 16000 });
  try {
    // decodeAudioData resamples into the context rate, so the channel data is already 16 kHz.
    const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
    return encodeWav(buf.getChannelData(0), 16000);
  } finally {
    void ctx.close();
  }
}

function encodeWav(samples: Float32Array, rate: number): Blob {
  const data = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const put = (at: number, s: string) => [...s].forEach((c, i) => data.setUint8(at + i, c.charCodeAt(0)));
  put(0, "RIFF");
  data.setUint32(4, 36 + samples.length * 2, true);
  put(8, "WAVE");
  put(12, "fmt ");
  data.setUint32(16, 16, true); // PCM chunk size
  data.setUint16(20, 1, true); // PCM
  data.setUint16(22, 1, true); // mono
  data.setUint32(24, rate, true);
  data.setUint32(28, rate * 2, true); // byte rate
  data.setUint16(32, 2, true); // block align
  data.setUint16(34, 16, true); // bits per sample
  put(36, "data");
  data.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    data.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([data.buffer], { type: "audio/wav" });
}
