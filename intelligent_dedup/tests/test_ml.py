import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from app.ml.vector_index import VectorIndex
from app.ml.embedder import ImageEmbedder, TextEmbedder

class TestVectorIndex:
    def test_vector_index_init_errors(self):
        # 1D instead of 2D
        with pytest.raises(ValueError):
            VectorIndex(np.array([1, 2, 3]), ["a"])
        # Length mismatch
        with pytest.raises(ValueError):
            VectorIndex(np.random.rand(2, 3), ["a"])

    def test_cosine_similarity(self):
        # Two identical vectors
        emb = np.array([[1, 0, 0], [1, 0, 0]], dtype=np.float32)
        idx = VectorIndex(emb, ["a", "b"])
        sims = idx.cosine_similarity_matrix()
        assert sims[0, 1] == pytest.approx(1.0)
        assert sims[1, 0] == pytest.approx(1.0)
        
        # Orthogonal vectors
        emb2 = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
        idx2 = VectorIndex(emb2, ["a", "b"])
        sims2 = idx2.cosine_similarity_matrix()
        assert sims2[0, 1] == pytest.approx(0.0)

    def test_find_similar_pairs(self):
        emb = np.array([
            [1, 0, 0],
            [0.99, 0.01, 0], # very similar to [1,0,0]
            [0, 1, 0]
        ], dtype=np.float32)
        idx = VectorIndex(emb, ["a", "b", "c"])
        pairs = idx.find_similar_pairs(threshold=0.95)
        # Should find (0,1) but not others
        assert len(pairs) == 1
        assert pairs[0][0] == 0
        assert pairs[0][1] == 1

    def test_clustering(self):
        # Two clusters: (a,b) and (c,d)
        emb = np.array([
            [1, 0, 0], [1, 0, 0], # group 1
            [0, 1, 0], [0, 1, 0], # group 2
            [0, 0, 1]            # unique
        ], dtype=np.float32)
        paths = ["a", "b", "c", "d", "e"]
        idx = VectorIndex(emb, paths)
        # Use a high threshold for pairs
        pairs = idx.find_similar_pairs(threshold=0.9)
        clusters = idx.cluster_by_similarity(pairs=pairs)
        assert len(clusters) == 2
        
        # Flatten and check contents
        flat = sorted([sorted(c) for c in clusters])
        assert flat == [["a", "b"], ["c", "d"]]

    def test_query(self):
        emb = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
        idx = VectorIndex(emb, ["a", "b"])
        # Query close to [1,0,0]
        q = np.array([0.9, 0.1, 0], dtype=np.float32)
        res = idx.query(q, top_k=1)
        assert res[0][0] == "a"
        assert res[0][1] > 0.8

class TestEmbedders:
    def test_image_embedder_mock(self):
        with patch("app.ml.embedder.ort.InferenceSession") as mock_session, \
             patch("app.ml.embedder._HAS_ORT", True), \
             patch("app.ml.embedder._HAS_PIL", True), \
             patch("pathlib.Path.exists", return_value=True):
            
            # Setup mock session behavior
            session_inst = mock_session.return_value
            session_inst.run.return_value = [np.random.rand(1, 1, 512)]
            
            embedder = ImageEmbedder()
            # Ensure session is assigned (even if _load_model was called, mock_session handles it)
            embedder._session = session_inst 
            
            with patch("app.ml.embedder.PILImage.open") as mock_open:
                mock_img = MagicMock()
                # Mock the resize/convert chain
                mock_img.convert.return_value.resize.return_value = np.zeros((256, 256, 3))
                mock_open.return_value = mock_img
                
                res = embedder.embed("fake.jpg")
                assert res is not None
                assert res.shape == (512,)

    def test_text_embedder_mock(self):
        with patch("app.ml.embedder.ort.InferenceSession") as mock_session, \
             patch("app.ml.embedder._HAS_ORT", True), \
             patch("app.ml.embedder._HAS_TRANSFORMERS", True), \
             patch("app.ml.embedder.AutoTokenizer.from_pretrained") as mock_tok_load:
            
            # Mock tokenizer
            mock_tok = MagicMock()
            mock_tok.return_value = {
                "input_ids": np.zeros((1, 10), dtype=np.int64),
                "attention_mask": np.ones((1, 10), dtype=np.int64)
            }
            mock_tok_load.return_value = mock_tok
            
            # Mock session
            session_inst = mock_session.return_value
            session_inst.run.return_value = [np.random.rand(1, 10, 384)]
            
            embedder = TextEmbedder()
            
            with patch("builtins.open", MagicMock()):
                with patch("app.ml.embedder.OnnxEmbedder._load_model"):
                    # Setting session manually since we mocked _load_model
                    embedder._session = session_inst
                    res = embedder.embed("fake.txt")
                    assert res is not None
                    assert res.shape == (384,)
