export async function readDraftStream(response, onProgress) {
  if (!response.ok) throw new Error(`Draft request failed (${response.status})`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  function event(line) {
    const value = JSON.parse(line);
    if (value.type === "error") throw new Error(value.detail);
    if (value.type === "result") return value.result;
    onProgress(value);
  }
  try {
    while (true) {
      const { done, value } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      const lines = pending.split("\n");
      pending = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const result = event(line);
        if (result !== undefined) return result;
      }
      if (done) {
        if (pending.trim()) {
          const result = event(pending);
          if (result !== undefined) return result;
        }
        throw new Error("Progress connection ended before completion. The run may still be active; do not automatically retry.");
      }
    }
  } finally { reader.releaseLock(); }
}
