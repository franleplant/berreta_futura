const { EventEmitter } = require("node:events");
const https = require("node:https");

const secret = process.env.MAGAZINE_TRACER_REVIEWER_SECRET;
const responseText = process.env.MAGAZINE_TRACER_REVIEWER_RESPONSE;
if (!secret || !responseText) throw new Error("tracer reviewer HTTPS preload requires test inputs");
const writerResponseText = process.env.MAGAZINE_TRACER_WRITER_RESPONSE;

const records = [];
https.request = (options, callback) => {
  const outgoing = new EventEmitter();
  outgoing.setTimeout = () => outgoing;
  outgoing.destroy = (error) => {
    if (error) process.nextTick(() => outgoing.emit("error", error));
  };
  outgoing.end = (body) => {
    records.push({ options, body: String(body) });
    let selectedResponse = responseText;
    try {
      const request = JSON.parse(String(body));
      const prompt = request.input?.[0]?.content?.[0]?.text;
      if (typeof prompt === "string" && prompt.includes("MAGAZINE CLOSED WRITER REQUEST")) {
        if (!writerResponseText) throw new Error("tracer writer response is unavailable");
        selectedResponse = writerResponseText;
      }
    } catch (error) {
      process.nextTick(() => outgoing.emit("error", error));
      return;
    }
    const response = new EventEmitter();
    response.statusCode = 200;
    response.headers = {};
    response.destroy = () => {};
    callback(response);
    process.nextTick(() => {
      response.emit("data", Buffer.from(selectedResponse, "utf8"));
      response.emit("end");
    });
  };
  return outgoing;
};

globalThis.__magazineTracerReviewerHttpsRecords = records;
