"""
Unit tests for UniversalIngestionPipeline.ingest_document()

Tests the core ingestion functionality after Neo4j removal.
Ensures:
1. Qdrant ingestion works
2. Method returns success (not error)
3. No AttributeErrors from missing Neo4j attributes
4. Proper metadata handling
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime


@pytest.fixture
def mock_qdrant_pipeline():
    """Mock the LlamaIndex IngestionPipeline"""
    pipeline = Mock()
    pipeline.run = Mock(return_value=[])
    return pipeline


@pytest.fixture
def mock_vector_store():
    """Mock Qdrant vector store"""
    store = Mock()
    return store


@pytest.fixture
def mock_embed_model():
    """Mock OpenAI embedding model"""
    model = Mock()
    return model


@pytest.fixture
def pipeline_instance(mock_qdrant_pipeline, mock_vector_store, mock_embed_model):
    """Create UniversalIngestionPipeline instance with mocked dependencies"""

    with patch('app.services.rag.pipeline.QdrantClient'), \
         patch('app.services.rag.pipeline.AsyncQdrantClient'), \
         patch('app.services.rag.pipeline.QdrantVectorStore', return_value=mock_vector_store), \
         patch('app.services.rag.pipeline.OpenAIEmbedding', return_value=mock_embed_model), \
         patch('app.services.rag.pipeline.IngestionPipeline', return_value=mock_qdrant_pipeline):

        from app.services.rag.pipeline import UniversalIngestionPipeline
        return UniversalIngestionPipeline()


@pytest.mark.asyncio
async def test_ingest_document_basic_success(pipeline_instance):
    """Test basic document ingestion succeeds"""

    test_doc = {
        'id': 123,
        'title': 'Test Document',
        'content': 'This is test content for a document.',
        'source': 'test',
        'document_type': 'document',
        'tenant_id': 'tenant123',
        'source_id': 'src123',
        'source_created_at': '2025-11-10T10:00:00Z'
    }

    result = await pipeline_instance.ingest_document(test_doc)

    # Should return success
    assert result['status'] == 'success', f"Expected success, got: {result}"
    assert result['document_id'] == '123'
    assert result['title'] == 'Test Document'
    assert 'error' not in result


@pytest.mark.asyncio
async def test_ingest_document_with_email_type(pipeline_instance):
    """Test email document ingestion"""

    test_email = {
        'id': 456,
        'title': 'Test Email',
        'content': 'Email body content here.',
        'source': 'gmail',
        'document_type': 'email',
        'tenant_id': 'tenant123',
        'source_id': 'email456',
        'source_created_at': '2025-11-10T12:00:00Z',
        'sender_name': 'John Doe',
        'sender_address': 'john@example.com',
        'to_addresses': ['jane@example.com']
    }

    result = await pipeline_instance.ingest_document(test_email)

    assert result['status'] == 'success'
    assert result['document_type'] == 'email'
    assert 'error' not in result


@pytest.mark.asyncio
async def test_ingest_document_no_attribute_errors(pipeline_instance):
    """CRITICAL: Ensure no AttributeErrors from missing Neo4j attributes"""

    test_doc = {
        'id': 789,
        'title': 'Test No Errors',
        'content': 'Content that should not trigger attribute errors.',
        'source': 'test',
        'document_type': 'document',
        'tenant_id': 'tenant123',
        'source_id': 'src789',
        'source_created_at': '2025-11-10T14:00:00Z'
    }

    # This should NOT raise AttributeError for:
    # - self.entity_extractor
    # - self.graph_store
    # - self.neo4j_driver
    # - self._reorder_labels_for_visualization()

    try:
        result = await pipeline_instance.ingest_document(test_doc)
        assert result['status'] == 'success'
        assert 'AttributeError' not in str(result.get('error', ''))
    except AttributeError as e:
        pytest.fail(f"AttributeError raised: {e}. This means dead code is still being executed!")


@pytest.mark.asyncio
async def test_ingest_document_metadata_handling(pipeline_instance):
    """Test proper metadata handling without Neo4j"""

    test_doc = {
        'id': 999,
        'title': 'Metadata Test',
        'content': 'Testing metadata extraction.',
        'source': 'gdrive',
        'document_type': 'pdf',
        'tenant_id': 'tenant123',
        'source_id': 'pdf999',
        'source_created_at': '2025-11-10T16:00:00Z',
        'file_url': 'https://storage.example.com/file.pdf',
        'file_size_bytes': 12345,
        'mime_type': 'application/pdf',
        'metadata': {
            'author': 'Test Author',
            'tags': ['important', 'review']
        }
    }

    result = await pipeline_instance.ingest_document(test_doc)

    assert result['status'] == 'success'
    assert result['document_id'] == '999'
    # Should handle metadata without trying to convert for Neo4j
    assert 'error' not in result


@pytest.mark.asyncio
async def test_ingest_document_qdrant_writes_succeed(pipeline_instance):
    """Test that Qdrant ingestion is actually called"""

    test_doc = {
        'id': 111,
        'title': 'Qdrant Test',
        'content': 'Testing Qdrant write path.',
        'source': 'test',
        'document_type': 'document',
        'tenant_id': 'tenant123',
        'source_id': 'src111'
    }

    result = await pipeline_instance.ingest_document(test_doc)

    # Verify qdrant_pipeline.run was called
    assert pipeline_instance.qdrant_pipeline.run.called
    call_args = pipeline_instance.qdrant_pipeline.run.call_args

    # Should have been called with documents list
    assert 'documents' in call_args.kwargs
    assert len(call_args.kwargs['documents']) == 1

    # Document should have correct doc_id
    doc = call_args.kwargs['documents'][0]
    assert doc.doc_id == '111'


@pytest.mark.asyncio
async def test_ingest_document_without_extract_entities_parameter():
    """Test that extract_entities parameter is no longer needed"""

    # This test ensures backward compatibility
    # Old code: await pipeline.ingest_document(doc, extract_entities=True)
    # New code: await pipeline.ingest_document(doc)

    with patch('app.services.rag.pipeline.QdrantClient'), \
         patch('app.services.rag.pipeline.AsyncQdrantClient'), \
         patch('app.services.rag.pipeline.QdrantVectorStore'), \
         patch('app.services.rag.pipeline.OpenAIEmbedding'), \
         patch('app.services.rag.pipeline.IngestionPipeline') as mock_pipeline:

        mock_pipeline.return_value.run = Mock(return_value=[])

        from app.services.rag.pipeline import UniversalIngestionPipeline
        pipeline = UniversalIngestionPipeline()

        test_doc = {
            'id': 222,
            'title': 'No Extract Entities',
            'content': 'Testing without extract_entities parameter.',
            'source': 'test',
            'document_type': 'document',
            'tenant_id': 'tenant123',
            'source_id': 'src222'
        }

        # Should work without extract_entities parameter
        result = await pipeline.ingest_document(test_doc)
        assert result['status'] == 'success'

        # Should also work with extract_entities=False (backward compat)
        result = await pipeline.ingest_document(test_doc, extract_entities=False)
        assert result['status'] == 'success'


@pytest.mark.asyncio
async def test_ingest_document_empty_content():
    """Test handling of document with empty content"""

    with patch('app.services.rag.pipeline.QdrantClient'), \
         patch('app.services.rag.pipeline.AsyncQdrantClient'), \
         patch('app.services.rag.pipeline.QdrantVectorStore'), \
         patch('app.services.rag.pipeline.OpenAIEmbedding'), \
         patch('app.services.rag.pipeline.IngestionPipeline') as mock_pipeline:

        mock_pipeline.return_value.run = Mock(return_value=[])

        from app.services.rag.pipeline import UniversalIngestionPipeline
        pipeline = UniversalIngestionPipeline()

        test_doc = {
            'id': 333,
            'title': 'Empty Content',
            'content': '',  # Empty content
            'source': 'test',
            'document_type': 'document',
            'tenant_id': 'tenant123',
            'source_id': 'src333'
        }

        result = await pipeline.ingest_document(test_doc)

        # Should handle gracefully (Qdrant will just create empty vector)
        # Not an error condition
        assert result['status'] in ['success', 'error']  # Either is acceptable
        if result['status'] == 'error':
            # If it errors, should be graceful, not AttributeError
            assert 'AttributeError' not in result.get('error', '')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
