import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def tool_results(body):
    found = []
    for message in body.get("messages", []):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                inner = block.get("content")
                if isinstance(inner, list):
                    inner = "".join(part.get("text", "") for part in inner if isinstance(part, dict))
                found.append(inner or "")
    return found


def offers_bash(body):
    return any(isinstance(tool, dict) and tool.get("name") == "Bash" for tool in body.get("tools") or [])


def events(blocks, stop_reason):
    yield "message_start", {
        "type": "message_start",
        "message": {
            "id": "msg_mock", "type": "message", "role": "assistant", "model": "claude-mock",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    }
    for index, block in enumerate(blocks):
        if block["type"] == "tool_use":
            yield "content_block_start", {"type": "content_block_start", "index": index, "content_block": {**block, "input": {}}}
            yield "content_block_delta", {"type": "content_block_delta", "index": index, "delta": {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}}
        else:
            yield "content_block_start", {"type": "content_block_start", "index": index, "content_block": {"type": "text", "text": ""}}
            yield "content_block_delta", {"type": "content_block_delta", "index": index, "delta": {"type": "text_delta", "text": block["text"]}}
        yield "content_block_stop", {"type": "content_block_stop", "index": index}
    yield "message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": 1}}
    yield "message_stop", {"type": "message_stop"}


class MockAnthropic:
    def __init__(self, script, final="done"):
        self.script = list(script)
        self.final = final
        self.results = []
        self.requests = 0
        self.lock = threading.Lock()
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                self.reply_json(404, {"type": "error", "error": {"type": "not_found_error", "message": "mock"}})

            def do_HEAD(self):
                self.send_response(200)
                self.end_headers()

            def do_POST(self):
                length = int(self.headers.get("content-length") or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    body = {}
                if self.path.split("?")[0].endswith("/count_tokens"):
                    self.reply_json(200, {"input_tokens": 1})
                    return
                blocks, stop = mock.answer(body)
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("content-type", "text/event-stream")
                    self.send_header("cache-control", "no-cache")
                    self.end_headers()
                    for name, data in events(blocks, stop):
                        self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
                        self.wfile.flush()
                    self.close_connection = True
                    return
                self.reply_json(200, {
                    "id": "msg_mock", "type": "message", "role": "assistant", "model": "claude-mock",
                    "content": blocks, "stop_reason": stop, "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                })

            def reply_json(self, code, payload):
                data = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def answer(self, body):
        with self.lock:
            self.requests += 1
            if not offers_bash(body):
                return [{"type": "text", "text": "ok"}], "end_turn"
            seen = tool_results(body)
            self.results = seen
            if len(seen) < len(self.script):
                step = dict(self.script[len(seen)])
                said = step.pop("say", None)
                use = {"type": "tool_use", "id": f"toolu_mock_{len(seen)}", "name": "Bash", "input": step}
                return ([{"type": "text", "text": said}] if said else []) + [use], "tool_use"
            return [{"type": "text", "text": self.final}], "end_turn"

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
