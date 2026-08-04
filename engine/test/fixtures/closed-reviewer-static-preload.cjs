const { EventEmitter } = require("node:events");
const https = require("node:https");

const secret = process.env.MAGAZINE_TRACER_REVIEWER_SECRET;
const responseText = process.env.MAGAZINE_TRACER_REVIEWER_RESPONSE;
if (!secret || !responseText) throw new Error("tracer reviewer HTTPS preload requires test inputs");

const records = [];
https.request = (options, callback) => {
  const outgoing = new EventEmitter();
  outgoing.setTimeout = () => outgoing;
  outgoing.destroy = (error) => {
    if (error) process.nextTick(() => outgoing.emit("error", error));
  };
  outgoing.end = (body) => {
    records.push({ options, body: String(body) });
    const response = new EventEmitter();
    response.statusCode = 200;
    response.headers = {};
    response.destroy = () => {};
    callback(response);
    process.nextTick(() => {
      response.emit("data", Buffer.from(responseText, "utf8"));
      response.emit("end");
    });
  };
  return outgoing;
};

globalThis.__magazineTracerReviewerHttpsRecords = records;
