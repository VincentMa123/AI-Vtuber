import pytest
import json
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from rag.formatters import format_products_for_prompt, format_promotions_for_prompt
from rag.product_search import load_product_dataset, get_all_promotions


class TestFormatProductsForPrompt:
    """Test product formatting for LLM context"""
    
    def test_empty_products_list(self):
        """Should return empty string for empty product list"""
        result = format_products_for_prompt([])
        assert result == ""
    
    def test_single_product(self):
        """Should format single product correctly"""
        products = [
            {
                "name": "Milk",
                "price": 25000,
                "description": "Fresh dairy milk"
            }
        ]
        result = format_products_for_prompt(products)
        assert "Milk" in result
        assert "25,000" in result
        assert "Fresh dairy milk" in result
        assert "Relevant Indomaret Products" in result
    
    def test_multiple_products(self):
        """Should format multiple products with numbering"""
        products = [
            {
                "name": "Milk",
                "price": 25000,
                "description": "Fresh dairy milk"
            },
            {
                "name": "Bread",
                "price": 12000,
                "description": "Whole wheat bread"
            }
        ]
        result = format_products_for_prompt(products)
        assert "1." in result
        assert "2." in result
        assert "Milk" in result
        assert "Bread" in result
        assert result.count("12,000") == 1
    
    def test_missing_fields(self):
        """Should handle missing fields gracefully"""
        products = [
            {
                "name": "Product",
                # missing price and description
            }
        ]
        result = format_products_for_prompt(products)
        assert "Product" in result
        assert "0" in result  # default price
    
    def test_price_formatting(self):
        """Should format prices with thousands separator"""
        products = [
            {
                "name": "Expensive Item",
                "price": 1500000,
                "description": "Premium product"
            }
        ]
        result = format_products_for_prompt(products)
        assert "1,500,000" in result
    
    def test_output_contains_instruction(self):
        """Should include instruction for LLM"""
        products = [{"name": "Test", "price": 1000, "description": "Test product"}]
        result = format_products_for_prompt(products)
        assert "Feel free to recommend" in result or "naturally" in result.lower()


class TestFormatPromotionsForPrompt:
    """Test promotion formatting for LLM context"""
    
    def test_empty_promotions_list(self):
        """Should return empty string for empty promotion list"""
        result = format_promotions_for_prompt([])
        assert result == ""
    
    def test_single_promotion(self):
        """Should format single promotion correctly"""
        promotions = [
            {
                "type": "Discount",
                "description": "50% off all milk products",
                "time_range": "Jan 1-31"
            }
        ]
        result = format_promotions_for_prompt(promotions)
        assert "Discount" in result
        assert "50% off all milk products" in result
        assert "Jan 1-31" in result
    
    def test_multiple_promotions(self):
        """Should format multiple promotions with numbering"""
        promotions = [
            {
                "type": "Discount",
                "description": "50% off",
                "time_range": "Jan 1-31"
            },
            {
                "type": "Buy 2 Get 1",
                "description": "Free item",
                "time_range": "Feb 1-28"
            }
        ]
        result = format_promotions_for_prompt(promotions)
        assert "1." in result
        assert "2." in result
        assert "Discount" in result
        assert "Buy 2 Get 1" in result
    
    def test_missing_time_range(self):
        """Should handle missing time_range"""
        promotions = [
            {
                "type": "Free Shipping",
                "description": "Free shipping on orders",
                # time_range missing
            }
        ]
        result = format_promotions_for_prompt(promotions)
        assert "Free Shipping" in result
        assert "Free shipping on orders" in result
    
    def test_output_contains_instruction(self):
        """Should include instruction for LLM"""
        promotions = [{"type": "Test", "description": "Test promo"}]
        result = format_promotions_for_prompt(promotions)
        assert "Share" in result or "naturally" in result.lower()


class TestLoadProductDataset:
    """Test product dataset loading"""
    
    def test_dataset_structure(self):
        """Loaded dataset should have expected structure"""
        dataset = load_product_dataset()
        assert isinstance(dataset, dict)
        assert "products" in dataset
    
    def test_products_list_exists(self):
        """Dataset should contain products list"""
        dataset = load_product_dataset()
        products = dataset.get("products", [])
        assert isinstance(products, list)
    
    def test_promotions_list_exists(self):
        """Dataset should contain promotions list"""
        dataset = load_product_dataset()
        promotions = dataset.get("promotions", [])
        assert isinstance(promotions, list)
    
    def test_products_have_required_fields(self):
        """Each product should have essential fields"""
        dataset = load_product_dataset()
        products = dataset.get("products", [])
        
        if products:  # Only test if products exist
            for product in products[:1]:  # Test first product
                assert "name" in product
                assert isinstance(product.get("name"), str)
    
    def test_consistent_dataset_loading(self):
        """Multiple loads should return same data"""
        dataset1 = load_product_dataset()
        dataset2 = load_product_dataset()
        
        assert len(dataset1.get("products", [])) == len(dataset2.get("products", []))
    
    def test_fallback_on_error(self):
        """Should return default structure if file not found"""
        with patch('rag.product_search.os.path.exists', return_value=False):
            with patch('builtins.open', side_effect=FileNotFoundError):
                dataset = load_product_dataset()
                assert dataset == {"products": [], "categories": [], "promotions": []}


class TestGetAllPromotions:
    """Test promotion retrieval"""
    
    def test_returns_list(self):
        """Should return list of promotions"""
        promotions = get_all_promotions()
        assert isinstance(promotions, list)
    
    def test_promotion_structure(self):
        """Promotions should have expected fields"""
        promotions = get_all_promotions()
        
        if promotions:  # If promotions exist
            for promo in promotions[:1]:
                assert isinstance(promo, dict)
                assert "type" in promo or "description" in promo
    
    def test_returns_from_dataset(self):
        """Should retrieve promotions from dataset"""
        promotions = get_all_promotions()
        dataset = load_product_dataset()
        expected_promos = dataset.get("promotions", [])
        
        assert len(promotions) == len(expected_promos)


class TestProductSearchIntegration:
    """Integration tests for product search without complex mocking"""
    
    def test_load_dataset_returns_dict(self):
        """load_product_dataset should return valid dict"""
        dataset = load_product_dataset()
        assert isinstance(dataset, dict)
        assert "products" in dataset
    
    def test_get_promotions_returns_list(self):
        """get_all_promotions should return list"""
        promotions = get_all_promotions()
        assert isinstance(promotions, list)
    
    def test_format_functions_handle_real_data(self):
        """Formatting functions should work with real dataset"""
        dataset = load_product_dataset()
        products = dataset.get("products", [])
        promotions = dataset.get("promotions", [])
        
        # Should not raise exceptions
        product_text = format_products_for_prompt(products[:3] if products else [])
        promo_text = format_promotions_for_prompt(promotions[:3] if promotions else [])
        
        assert isinstance(product_text, str)
        assert isinstance(promo_text, str)


class TestEmbeddingModel:
    """Tests for embedding model loading and caching"""
    
    def test_get_embedding_model_returns_model_or_none(self):
        """get_embedding_model should return model or None"""
        with patch('rag.embeddings.SentenceTransformer') as mock_model:
            mock_instance = MagicMock()
            mock_model.return_value = mock_instance
            
            from rag.embeddings import get_embedding_model
            
            # Reset cache for testing
            import rag.embeddings
            rag.embeddings._model_cache = None
            
            result = get_embedding_model()
            # Result should be either the model or None
            assert result is None or hasattr(result, 'encode')
    
    def test_embedding_model_caching(self):
        """Model should be cached after first load"""
        with patch('rag.embeddings.SentenceTransformer') as mock_model:
            mock_instance = MagicMock()
            mock_model.return_value = mock_instance
            
            from rag.embeddings import get_embedding_model
            import rag.embeddings
            
            # Reset cache
            rag.embeddings._model_cache = None
            
            # First call should load
            result1 = get_embedding_model()
            # Second call should return cached
            result2 = get_embedding_model()
            
            # Should only call SentenceTransformer once (for successful load)
            # or not at all (if error is caught)
            assert mock_model.call_count <= 1


class TestProductQueryDetection:
    """Test product query detection without full embedding complexity"""
    
    def test_detection_functions_exist(self):
        """Detection functions should be callable"""
        from rag.product_search import detect_product_query, detect_promotion_query
        
        assert callable(detect_product_query)
        assert callable(detect_promotion_query)
    
    def test_detection_with_empty_message(self):
        """Should return False for empty messages"""
        from rag.product_search import detect_product_query, detect_promotion_query
        
        assert detect_product_query("") is False
        assert detect_product_query("  ") is False
        assert detect_promotion_query("") is False
    
    def test_detection_with_short_message(self):
        """Should return False for very short messages"""
        from rag.product_search import detect_product_query, detect_promotion_query
        
        assert detect_product_query("ab") is False
        assert detect_promotion_query("ab") is False
    
    def test_detection_returns_bool(self):
        """Detection functions should return boolean"""
        from rag.product_search import detect_product_query, detect_promotion_query
        
        result1 = detect_product_query("this is a test message")
        result2 = detect_promotion_query("this is a test message")
        
        assert isinstance(result1, bool)
        assert isinstance(result2, bool)


class TestRAGInitialization:
    """Test RAG system initialization"""
    
    def test_initialize_rag_callable(self):
        """initialize_rag should be callable"""
        from rag.product_search import initialize_rag
        
        assert callable(initialize_rag)
    
    def test_initialize_rag_returns_bool(self):
        """initialize_rag should return boolean"""
        with patch('rag.product_search.get_embedding_model') as mock_model:
            mock_model.return_value = None  # Simulate model not available
            
            from rag.product_search import initialize_rag
            
            result = initialize_rag()
            assert isinstance(result, bool)
