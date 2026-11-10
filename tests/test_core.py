import copy
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Store, Problem, digest
from tts import sentences


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.state = self.store.read()
        self.ch = self.state["chapters"][0]
        self.save("Prima frase. Una frase da migliorare. Ultima frase.")

    def tearDown(self):
        self.temp.cleanup()

    def call(self, method, **payload):
        result = getattr(self.store, method)({"revision": self.state["revision"], **payload})
        self.state = result["state"]
        self.ch = self.state["chapters"][0]
        return result

    def save(self, text):
        return self.call("save_chapter", chapter_id=self.ch["id"], title="Prova", text=text)

    def request(self, text="Una frase da migliorare.", comment="Rendi più concreta."):
        start = self.ch["text"].index(text)
        return self.call("add_request", chapter_id=self.ch["id"], start=start, end=start+len(text), original=text, comment=comment)["request_id"]

    def export(self):
        return self.call("export_batch")["package"]

    def response(self, package, replacements=None):
        data = copy.deepcopy(package["response_template"])
        for change in data["changes"]:
            change.update(replacement=(replacements or {}).get(change["request_id"], "Una porta sbatté."), reason="Più concreto.")
        return data

    def test_complete_roundtrip_and_idempotency(self):
        request_id = self.request()
        package = self.export()
        response = self.response(package)
        original = self.ch["text"]
        result = self.call("import_response", response=response)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(original, self.ch["text"])
        self.assertEqual(self.call("import_response", response=response)["skipped"], 1)
        self.call("resolve", request_id=request_id, action="apply")
        self.assertIn("Una porta sbatté.", self.ch["text"])
        with self.assertRaises(Problem):
            self.call("resolve", request_id=request_id, action="apply")
        self.assertEqual(self.call("import_response", response=response)["skipped"], 1)

    def test_rebase_outside_selection(self):
        request_id = self.request()
        package = self.export()
        self.save("Nuova introduzione. " + self.ch["text"])
        self.call("import_response", response=self.response(package))
        self.assertFalse(self.state["requests"][0]["conflict"])
        self.call("resolve", request_id=request_id, action="apply")
        self.assertTrue(self.ch["text"].startswith("Nuova introduzione."))

    def test_edited_selection_is_never_overwritten(self):
        request_id = self.request()
        package = self.export()
        self.save(self.ch["text"].replace("da migliorare", "già corretta"))
        self.call("import_response", response=self.response(package))
        self.assertTrue(self.state["requests"][0]["conflict"])
        with self.assertRaises(Problem):
            self.call("resolve", request_id=request_id, action="apply")
        self.assertIn("già corretta", self.ch["text"])

    def test_overlapping_requests_are_blocked(self):
        first = self.request()
        second = self.request("frase da migliorare")
        package = self.export()
        self.call("import_response", response=self.response(package))
        self.call("resolve", request_id=first, action="apply")
        self.assertTrue(next(x for x in self.state["requests"] if x["id"] == second)["conflict"])
        with self.assertRaises(Problem):
            self.call("resolve", request_id=second, action="apply")

    def test_nonoverlapping_updates_move_offsets_exactly(self):
        first = self.request("Prima frase.")
        second = self.request("Ultima frase.")
        package = self.export()
        self.call("import_response", response=self.response(package,{first:"Inizio molto più lungo e diverso.",second:"Fine."}))
        self.call("resolve", request_id=first, action="apply")
        self.call("resolve", request_id=second, action="apply")
        self.assertEqual(self.ch["text"], "Inizio molto più lungo e diverso. Una frase da migliorare. Fine.")

    def test_deletion_is_explicit_and_reversible(self):
        request_id = self.request()
        original = self.ch["text"]
        package = self.export()
        self.call("import_response", response=self.response(package,{request_id:""}))
        self.call("resolve", request_id=request_id, action="apply")
        self.assertNotIn("da migliorare", self.ch["text"])
        self.call("undo")
        self.assertEqual(original,self.ch["text"])
        self.assertEqual(self.state["requests"][0]["status"],"proposed")

    def test_response_validation_is_atomic(self):
        self.request()
        self.request("Ultima frase.")
        package = self.export()
        response = self.response(package)
        response["changes"][1]["original"] = "Testo alterato"
        before = self.store.read()
        with self.assertRaises(Problem):
            self.call("import_response", response=response)
        self.assertEqual(before,self.store.read())

    def test_foreign_book_batch_and_duplicate_ids_rejected(self):
        self.request()
        package = self.export()
        for mutate in (lambda r:r.update(book_id="other"),lambda r:r.update(batch_id="other"),lambda r:r["changes"].append(copy.deepcopy(r["changes"][0]))):
            response = self.response(package)
            mutate(response)
            with self.assertRaises(Problem):
                self.call("import_response", response=response)

    def test_stale_tabs_and_wrong_unicode_offsets(self):
        with self.assertRaises(Problem):
            self.store.settings({"revision":0,"title":"stale"})
        self.save("È già qui. 🙂 L’acqua cade. Fine.")
        self.request("L’acqua cade.")
        self.assertEqual(self.state["requests"][0]["original"],"L’acqua cade.")
        with self.assertRaises(Problem):
            self.call("add_request",chapter_id=self.ch["id"],start=14,end=26,original="L’acqua cade.",comment="Prova")

    def test_pending_batches_survive_undo_export(self):
        self.request()
        package = self.export()
        self.call("undo")
        self.assertEqual(len(self.state["batches"]),1)
        self.call("import_response",response=self.response(package))

    def test_backup_restore_and_undo_across_books(self):
        self.request()
        package=self.export()
        project=copy.deepcopy(self.state)
        self.call("restore",project=project)
        self.assertEqual(self.state["requests"],project["requests"])
        self.assertTrue(self.store.backup().is_file())
        other=copy.deepcopy(project);other["book_id"]="new-book";other["batches"]=[];other["requests"]=[]
        self.call("restore",project=other)
        self.call("undo")
        self.assertEqual(self.state["book_id"],project["book_id"])

    def test_malformed_backup_rejected_before_mutation(self):
        bad=copy.deepcopy(self.state);bad["requests"]=[{"id":"bad"}]
        before=self.store.read()
        with self.assertRaises(Problem):self.call("restore",project=bad)
        self.assertEqual(before,self.store.read())

    def test_segment_offsets_keep_exact_original(self):
        text='Il dott. Rossi arrivò. «È già qui?»\n\n🙂 Nessuno rispose. Un ultimo frammento'
        units=sentences(text)
        self.assertEqual(units[0]["text"],"Il dott. Rossi arrivò.")
        for unit in units:self.assertEqual(text[unit["start"]:unit["end"]],unit["text"])
        self.assertEqual(len(units),4)

    def test_long_unpunctuated_text_has_bounded_speech_chunks(self):
        text="parola "*700
        units=sentences(text)
        self.assertTrue(all(len(u["text"])<=900 for u in units))
        self.assertEqual(' '.join(u["text"] for u in units).split(),text.split())


if __name__ == "__main__":
    unittest.main()
