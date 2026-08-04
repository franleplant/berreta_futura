const { EventEmitter } = require("node:events");
const https = require("node:https");

const secret = process.env.CLOSED_WRITER_TEST_SECRET;
const responseText = process.env.CLOSED_WRITER_TEST_RESPONSE;
if (!secret || !responseText) throw new Error("closed writer HTTPS preload requires test inputs");

const records = [];
let calls = 0;
https.request = (options, callback) => {
  const outgoing = new EventEmitter();
  outgoing.setTimeout = () => outgoing;
  outgoing.destroy = (error) => {
    if (error) process.nextTick(() => outgoing.emit("error", error));
  };
  outgoing.end = (body) => {
    calls += 1;
    records.push({ options, body: String(body) });
    if (calls === 1) {
      process.nextTick(() => outgoing.emit("error", new Error("temporary network failure")));
      return;
    }
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

globalThis.__closedWriterHttpsRecords = records;
