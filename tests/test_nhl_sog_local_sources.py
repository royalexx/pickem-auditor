import unittest,tempfile,hashlib,zipfile,io,json
from pathlib import Path
from v2.nhl_sog_local_sources import stage_pool,publish_bundle,open_history_sources,copy_members

class LocalSourcesTests(unittest.TestCase):
    def test_exact_bytes_roundtrip_and_immutable_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'raw_http_body'/'test.bin';p.parent.mkdir();p.write_bytes(b'original bytes')
            local=stage_pool(root);self.assertEqual((local/'raw_http_body/test.bin').read_bytes(),b'original bytes')
            doc,ref=publish_bundle(root,local,{'created_at':'2026-11-19T19:00:00Z'})
            before=(root/doc['source_bundle']['path']).read_bytes()
            restored=open_history_sources(root,doc)
            self.assertEqual((restored/'raw_http_body/test.bin').read_bytes(),p.read_bytes())
            self.assertEqual(hashlib.sha256(before).hexdigest(),doc['source_bundle']['sha256'])
            (root/doc['source_bundle']['path']).write_bytes(before+b'changed')
            with self.assertRaisesRegex(ValueError,'HASH_DRIFT'):open_history_sources(root,doc)
    def test_original_source_packet_preserves_signed_bytes_and_clock(self):
        from v2.nhl_sog_source_packets import persist_packet
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as stage:
            local=Path(stage);r={'archive_path':'raw_http_body/body.bin','collector_proof_archive_path':'c03_collector_receipts/proof.json','received_at':'2026-11-19T20:00:00Z'}
            for rel,raw in ((r['archive_path'],b'original HTTP bytes'),(r['collector_proof_archive_path'],b'original HMAC proof')):
                p=local/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            a=persist_packet(tmp,local,r);b=persist_packet(tmp,local,r)
            self.assertEqual(a,b);self.assertEqual(r['received_at'],'2026-11-19T20:00:00Z')
            with zipfile.ZipFile(Path(tmp)/a['path']) as z:
                for rel in (r['archive_path'],r['collector_proof_archive_path']):self.assertEqual(z.read(rel),(local/rel).read_bytes())
    def test_zip_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as z:z.writestr('../escape','bad')
            raw=buf.getvalue();(root/'bad.zip').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'UNSAFE'):open_history_sources(root,{'source_bundle':{'path':'bad.zip','sha256':hashlib.sha256(raw).hexdigest()}})
    def test_copy_members_rejects_escape(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            with self.assertRaisesRegex(ValueError,'UNSAFE'):copy_members(a,b,['../secret'])

if __name__=='__main__':unittest.main()
