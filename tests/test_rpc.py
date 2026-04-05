"""Tests for the JSON-RPC framework."""

import json

import cymongoose as cm


class TestRpcBasic:
    def test_simple_method(self):
        rpc = cm.Rpc()

        def echo(req):
            val = cm.json_get(req.frame, "$.params")
            req.ok(val)

        rpc.add("echo", echo)
        resp = rpc.process('{"id":1,"method":"echo","params":[1,2,3]}')
        parsed = json.loads(resp)
        assert parsed["id"] == 1
        assert parsed["result"] == [1, 2, 3]

    def test_string_result(self):
        rpc = cm.Rpc()

        def greet(req):
            name = cm.json_get_str(req.frame, "$.params[0]")
            req.ok(json.dumps(f"hello {name}"))

        rpc.add("greet", greet)
        resp = rpc.process('{"id":1,"method":"greet","params":["world"]}')
        parsed = json.loads(resp)
        assert parsed["result"] == "hello world"

    def test_numeric_result(self):
        rpc = cm.Rpc()

        def add(req):
            a = cm.json_get_num(req.frame, "$.params[0]")
            b = cm.json_get_num(req.frame, "$.params[1]")
            req.ok(str(a + b))

        rpc.add("add", add)
        resp = rpc.process('{"id":1,"method":"add","params":[3,4]}')
        parsed = json.loads(resp)
        assert parsed["result"] == 7


class TestRpcError:
    def test_explicit_error(self):
        rpc = cm.Rpc()

        def fail(req):
            req.err(-32000, "something broke")

        rpc.add("fail", fail)
        resp = rpc.process('{"id":1,"method":"fail"}')
        parsed = json.loads(resp)
        assert parsed["error"]["code"] == -32000
        assert parsed["error"]["message"] == "something broke"

    def test_exception_becomes_error(self):
        rpc = cm.Rpc()

        def boom(req):
            raise ValueError("bad value")

        rpc.add("boom", boom)
        resp = rpc.process('{"id":1,"method":"boom"}')
        parsed = json.loads(resp)
        assert parsed["error"]["code"] == -32603
        assert "bad value" in parsed["error"]["message"]

    def test_unknown_method(self):
        rpc = cm.Rpc()
        resp = rpc.process('{"id":1,"method":"nonexistent"}')
        parsed = json.loads(resp)
        assert parsed["error"]["code"] == -32601

    def test_no_response_from_handler(self):
        rpc = cm.Rpc()

        def noop(req):
            pass  # handler forgets to call ok() or err()

        rpc.add("noop", noop)
        resp = rpc.process('{"id":1,"method":"noop"}')
        parsed = json.loads(resp)
        assert parsed["error"]["code"] == -32603


class TestRpcNotification:
    def test_notification_no_id(self):
        """JSON-RPC notifications (no id) should produce no response."""
        rpc = cm.Rpc()
        called = []

        def handler(req):
            called.append(True)
            req.ok("null")

        rpc.add("notify", handler)
        resp = rpc.process('{"method":"notify"}')
        # mg_rpc_ok skips output when there's no $.id
        assert resp == "" or "id" not in json.loads(resp) if resp else True
        assert called


class TestRpcMethods:
    def test_methods_list(self):
        rpc = cm.Rpc()
        rpc.add("add", lambda r: r.ok("0"))
        rpc.add("sub", lambda r: r.ok("0"))
        methods = rpc.methods
        assert "add" in methods
        assert "sub" in methods

    def test_empty_methods(self):
        rpc = cm.Rpc()
        assert rpc.methods == []


class TestRpcReqValidation:
    def test_double_ok_raises(self):
        rpc = cm.Rpc()
        errors = []

        def bad(req):
            req.ok("1")
            try:
                req.ok("2")
            except RuntimeError as e:
                errors.append(str(e))

        rpc.add("bad", bad)
        rpc.process('{"id":1,"method":"bad"}')
        assert errors and "already sent" in errors[0]

    def test_double_err_raises(self):
        rpc = cm.Rpc()
        errors = []

        def bad(req):
            req.err(-1, "first")
            try:
                req.err(-2, "second")
            except RuntimeError as e:
                errors.append(str(e))

        rpc.add("bad", bad)
        rpc.process('{"id":1,"method":"bad"}')
        assert errors and "already sent" in errors[0]
