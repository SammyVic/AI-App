import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from app.ml.vector_index import VectorIndex
from app.ml.embedder import ImageEmbedder, TextEmbedder

class TestVectorIndex:

    def test_vector_index_init_errors(self):
        """This advanced machine learning test meticulously validates the embedding generation and vector similarity search logic for identifying visually similar or contextually related files in large and diverse dataset collections."""
        with pytest.raises(ValueError):
            VectorIndex(np.array([1, 2, 3]), ['a'])
        with pytest.raises(ValueError):
            VectorIndex(np.random.rand(2, 3), ['a'])

    def test_cosine_similarity(self):
        """This advanced machine learning test meticulously validates the embedding generation and vector similarity search logic for identifying visually similar or contextually related files in large and diverse dataset collections."""
        emb = np.array([[1, 0, 0], [1, 0, 0]], dtype=np.float32)
        idx = VectorIndex(emb, ['a', 'b'])
        sims = idx.cosine_similarity_matrix()
        assert sims[0, 1] == pytest.approx(1.0)
        assert sims[1, 0] == pytest.approx(1.0)
        emb2 = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
        idx2 = VectorIndex(emb2, ['a', 'b'])
        sims2 = idx2.cosine_similarity_matrix()
        assert sims2[0, 1] == pytest.approx(0.0)

    def test_find_similar_pairs(self):
        """This advanced machine learning test meticulously validates the embedding generation and vector similarity search logic for identifying visually similar or contextually related files in large and diverse dataset collections."""
        emb = np.array([[1, 0, 0], [0.99, 0.01, 0], [0, 1, 0]], dtype=np.float32)
        idx = VectorIndex(emb, ['a', 'b', 'c'])
        pairs = idx.find_similar_pairs(threshold=0.95)
        assert len(pairs) == 1
        assert pairs[0][0] == 0
        assert pairs[0][1] == 1

    def test_clustering(self):
        """This advanced machine learning test meticulously validates the embedding generation and vector similarity search logic for identifying visually similar or contextually related files in large and diverse dataset collections."""
        emb = np.array([[1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
        paths = ['a', 'b', 'c', 'd', 'e']
        idx = VectorIndex(emb, paths)
        pairs = idx.find_similar_pairs(threshold=0.9)
        clusters = idx.cluster_by_similarity(pairs=pairs)
        assert len(clusters) == 2
        flat = sorted([sorted(c) for c in clusters])
        assert flat == [['a', 'b'], ['c', 'd']]

    def test_query(self):
        """This advanced machine learning test meticulously validates the embedding generation and vector similarity search logic for identifying visually similar or contextually related files in large and diverse dataset collections."""
        emb = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
        idx = VectorIndex(emb, ['a', 'b'])
        q = np.array([0.9, 0.1, 0], dtype=np.float32)
        res = idx.query(q, top_k=1)
        assert res[0][0] == 'a'
        assert res[0][1] > 0.8

class TestEmbedders:

    def test_image_embedder_mock(self):
        """This advanced machine learning test meticulously validates the embedding generation and vector similarity search logic for identifying visually similar or contextually related files in large and diverse dataset collections."""
        with patch('app.ml.embedder.ort.InferenceSession') as mock_session, patch('app.ml.embedder._HAS_ORT', True), patch('app.ml.embedder._HAS_PIL', True), patch('pathlib.Path.exists', return_value=True):
            session_inst = mock_session.return_value
            session_inst.run.return_value = [np.random.rand(1, 1, 512)]
            embedder = ImageEmbedder()
            embedder._session = session_inst
            with patch('app.ml.embedder.PILImage.open') as mock_open:
                mock_img = MagicMock()
                mock_img.convert.return_value.resize.return_value = np.zeros((256, 256, 3))
                mock_open.return_value = mock_img
                res = embedder.embed('fake.jpg')
                assert res is not None
                assert res.shape == (512,)

    def test_text_embedder_mock(self):
        """This advanced machine learning test meticulously validates the embedding generation and vector similarity search logic for identifying visually similar or contextually related files in large and diverse dataset collections."""
        with patch('app.ml.embedder.ort.InferenceSession') as mock_session, patch('app.ml.embedder._HAS_ORT', True), patch('app.ml.embedder._HAS_TRANSFORMERS', True), patch('app.ml.embedder.AutoTokenizer.from_pretrained') as mock_tok_load:
            mock_tok = MagicMock()
            mock_tok.return_value = {'input_ids': np.zeros((1, 10), dtype=np.int64), 'attention_mask': np.ones((1, 10), dtype=np.int64)}
            mock_tok_load.return_value = mock_tok
            session_inst = mock_session.return_value
            session_inst.run.return_value = [np.random.rand(1, 10, 384)]
            embedder = TextEmbedder()
            with patch('builtins.open', MagicMock()):
                with patch('app.ml.embedder.OnnxEmbedder._load_model'):
                    embedder._session = session_inst
                    res = embedder.embed('fake.txt')
                    assert res is not None
                    assert res.shape == (384,)