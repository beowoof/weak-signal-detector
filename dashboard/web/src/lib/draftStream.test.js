import test from "node:test";
import assert from "node:assert/strict";
import { readDraftStream } from "./draftStream.js";

test("streams split events and does not lose progress before the result", async () => {
  const encoder = new TextEncoder();
  const response = new Response(new ReadableStream({ start(controller) {
    for (const chunk of ['{"type":"progress","stage":"Retr', 'ieval failed"}\n{"type":"result","result":{"notes":"done"}}\n']) controller.enqueue(encoder.encode(chunk));
    controller.close();
  }}));
  const stages = [];
  assert.deepEqual(await readDraftStream(response, event => stages.push(event.stage)), { notes: "done" });
  assert.deepEqual(stages, ["Retrieval failed"]);
});

test("an interrupted connection is not mistaken for completion", async () => {
  await assert.rejects(readDraftStream(new Response('{"type":"progress"}\n'), () => {}), /may still be active/);
});
