import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import create_server


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.server=create_server(cls.temp.name)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(5)
        cls.server.speech.close()
        cls.temp.cleanup()

    def request(self,path,method="GET",data=None,headers=None):
        connection=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=10)
        try:
            connection.request(method,path,body=json.dumps(data) if data is not None else None,headers=headers or {})
            response=connection.getresponse()
            return response.status,dict(response.getheaders()),response.read()
        finally:
            connection.close()

    def test_mutation_requires_token(self):
        status,_,_=self.request("/api/settings","POST",{"title":"forged"})
        self.assertEqual(status,403)

    def test_foreign_origin_rejected_even_with_token(self):
        status,_,_=self.request("/api/settings","POST",{},
                               {"X-BookForge-Token":self.server.token,"Origin":"https://example.com"})
        self.assertEqual(status,403)

    def test_dns_rebinding_host_rejected(self):
        status,_,_=self.request("/api/state",headers={"Host":"example.com"})
        self.assertEqual(status,403)

    def test_static_files_are_allowlisted(self):
        status,_,_=self.request("/../core.py")
        self.assertEqual(status,404)
        status,headers,body=self.request("/app.js")
        self.assertEqual(status,200)
        self.assertIn("script-src 'self'",headers["Content-Security-Policy"])

    def test_state_is_local_and_can_be_retrieved(self):
        status,_,body=self.request("/api/state")
        self.assertEqual(status,200)
        data=json.loads(body)
        self.assertEqual(data["token"],self.server.token)
        self.assertEqual(data["state"]["schema"],"bookforge.project.v1")


if __name__=="__main__":
    unittest.main()
