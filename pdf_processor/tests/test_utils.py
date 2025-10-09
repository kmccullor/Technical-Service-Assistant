import sys
import types

import pdf_processor.utils as utils


def test_chunk_text_monkeypatch():
    # Create a fake nltk module to avoid external downloads during tests
    fake_nltk = types.SimpleNamespace()
    fake_nltk.data = types.SimpleNamespace(
        find=lambda x: None,
        download=lambda name, quiet=True: None,
    )

    def sent_tokenize(para):
        if not para:
            return []
        # naive sentence split for tests
        parts = [p.strip() for p in para.replace("\n", " ").split(". ") if p.strip()]
        return [p if p.endswith(".") else p + "." for p in parts]

    fake_nltk.tokenize = types.SimpleNamespace(sent_tokenize=sent_tokenize)

    old = sys.modules.get("nltk")
    sys.modules["nltk"] = fake_nltk
    try:
        text = "Hello world. This is a test.\n\nNew para. More."
        chunks, next_index = utils.chunk_text(text, "doc1", start_index=0)
        assert next_index > 0
        assert any("Hello" in c["text"] for c in chunks)
        # metadata checks
        assert all("metadata" in c and "document" in c["metadata"] for c in chunks)
    finally:
        if old is None:
            del sys.modules["nltk"]
        else:
            sys.modules["nltk"] = old


def test_chunk_tables():
    tables = [[{"col1": "a", "col2": "b"}, {"col1": "c"}]]
    chunks, next_index = utils.chunk_tables(tables, "doc", 5)
    assert len(chunks) == 2
    assert chunks[0]["chunk_index"] == 5
    assert "col1" in chunks[0]["text"]


def test_chunk_images(tmp_path):
    img1 = tmp_path / "img1.png"
    img1.write_text("x")
    img2 = tmp_path / "img2.png"
    img2.write_text("x")
    paths = [str(img1), str(img2)]
    chunks, next_index = utils.chunk_images(paths, "doc", 0)
    assert len(chunks) == 2
    assert "img1.png" in chunks[0]["text"]


def test_get_embedding(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embedding": [0.1, 0.2, 0.3]}

    fake_requests = types.SimpleNamespace(post=lambda url, json: FakeResp())
    monkeypatch.setattr(utils, "requests", fake_requests)
    emb = utils.get_embedding("hello", model="m", ollama_url="u")
    assert emb == [0.1, 0.2, 0.3]


def test_setup_logger(tmp_path):
    logdir = str(tmp_path)
    logger = utils.setup_logger("testprog", log_dir=logdir)
    logger.info("testing")
    # Ensure at least one file created with program name
    files = list(tmp_path.iterdir())
    assert any("testprog" in f.name for f in files)
