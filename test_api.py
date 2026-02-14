"""
Complete Flask App Example - Klikindomaret Product API
This is a ready-to-run web service that handles token refresh automatically
UPDATED with correct search endpoint!
"""

from flask import Flask, jsonify, request, render_template_string
from klikindomaret_playwright import TokenManager, KlikIndomaretAPI
import atexit
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize token manager (runs in background)
print("🚀 Initializing Klikindomaret API service...")
token_manager = TokenManager()
token_manager.start()
api = KlikIndomaretAPI(token_manager)

# Clean up on shutdown
atexit.register(lambda: token_manager.stop())

# HTML template for testing
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Klikindomaret API Service</title>
    <style>
        body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
        .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .example { background: #e8f4f8; padding: 10px; margin: 5px 0; border-left: 3px solid #2196F3; }
        input { padding: 8px; width: 300px; margin-right: 10px; }
        button { padding: 8px 15px; background: #4CAF50; color: white; border: none; cursor: pointer; }
        button:hover { background: #45a049; }
        .result { background: #fff; border: 1px solid #ddd; padding: 15px; margin-top: 10px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <h1>🛒 Klikindomaret API Service</h1>
    <p>Status: <strong style="color: green;">✓ Running</strong></p>
    
    <h2>Available Endpoints</h2>
    
    <div class="endpoint">
        <h3>1. Get Product Details</h3>
        <p><code>GET /api/product/&lt;permalink&gt;</code></p>
        <div class="example">
            <strong>Try it:</strong><br>
            <input type="text" id="permalink" value="kental-manis-3" placeholder="Enter product permalink">
            <button onclick="getProduct()">Get Product</button>
            <div id="product-result" class="result" style="display:none;"></div>
        </div>
    </div>
    
    <div class="endpoint">
        <h3>2. Search Products</h3>
        <p><code>GET /api/search?q=&lt;query&gt;&page=&lt;page&gt;</code></p>
        <div class="example">
            <strong>Try it:</strong><br>
            <input type="text" id="search-query" value="indomilk" placeholder="Enter search term">
            <button onclick="searchProducts()">Search</button>
            <div id="search-result" class="result" style="display:none;"></div>
        </div>
    </div>
    
    <div class="endpoint">
        <h3>3. Service Status</h3>
        <p><code>GET /api/status</code></p>
        <button onclick="checkStatus()">Check Status</button>
        <div id="status-result" class="result" style="display:none;"></div>
    </div>
    
    <script>
        async function getProduct() {
            const permalink = document.getElementById('permalink').value;
            const result = document.getElementById('product-result');
            result.style.display = 'block';
            result.textContent = 'Loading...';
            
            try {
                const response = await fetch(`/api/product/${permalink}`);
                const data = await response.json();
                result.textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                result.textContent = 'Error: ' + error.message;
            }
        }
        
        async function searchProducts() {
            const query = document.getElementById('search-query').value;
            const result = document.getElementById('search-result');
            result.style.display = 'block';
            result.textContent = 'Loading...';
            
            try {
                const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                result.textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                result.textContent = 'Error: ' + error.message;
            }
        }
        
        async function checkStatus() {
            const result = document.getElementById('status-result');
            result.style.display = 'block';
            result.textContent = 'Loading...';
            
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                result.textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                result.textContent = 'Error: ' + error.message;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    """Home page with API documentation"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def status():
    """Check service status"""
    token_status = "valid" if token_manager.token else "not initialized"
    
    return jsonify({
        'status': 'running',
        'token_status': token_status,
        'token_expires_at': token_manager.token_expires_at.isoformat() if token_manager.token_expires_at else None,
        'endpoints': {
            'product': '/api/product/<permalink>',
            'search': '/api/search?q=<query>&page=<page>',
            'status': '/api/status'
        }
    })

@app.route('/api/product/<permalink>')
def get_product(permalink):
    """
    Get product details by permalink
    
    Example: /api/product/kental-manis-3
    """
    try:
        # Optional parameters
        store_code = request.args.get('store_code', 'TJKT')
        latitude = float(request.args.get('latitude', -6.1763897))
        longitude = float(request.args.get('longitude', 106.82667))
        
        # Get product data
        data = api.get_product(
            permalink,
            storeCode=store_code,
            latitude=latitude,
            longitude=longitude
        )
        
        return jsonify(data)
        
    except Exception as e:
        app.logger.error(f"Error getting product {permalink}: {str(e)}")
        return jsonify({
            'error': str(e),
            'permalink': permalink
        }), 500

@app.route('/api/search')
def search_products():
    """
    Search for products - FIXED with correct endpoint!
    
    Parameters:
    - q: Search query (required)
    - page: Page number (default: 0, starts at 0!)
    - size: Results per page (default: 15)
    
    Example: /api/search?q=indomilk&page=0&size=10
    """
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({
            'error': 'Query parameter "q" is required',
            'example': '/api/search?q=indomilk'
        }), 400
    
    try:
        page = int(request.args.get('page', 0))  # Starts at 0!
        size = int(request.args.get('size', 15))
        
        # Search products with correct method signature
        data = api.search(query, page=page, size=size)
        
        return jsonify(data)
        
    except Exception as e:
        app.logger.error(f"Error searching for '{query}': {str(e)}")
        return jsonify({
            'error': str(e),
            'query': query
        }), 500

@app.route('/api/batch/products', methods=['POST'])
def batch_products():
    """
    Get multiple products in one request
    
    POST body: {"permalinks": ["product-1", "product-2", ...]}
    """
    try:
        data = request.get_json()
        permalinks = data.get('permalinks', [])
        
        if not permalinks:
            return jsonify({
                'error': 'No permalinks provided',
                'example': {'permalinks': ['product-1', 'product-2']}
            }), 400
        
        results = []
        for permalink in permalinks:
            try:
                product_data = api.get_product(permalink)
                results.append({
                    'permalink': permalink,
                    'success': True,
                    'data': product_data
                })
            except Exception as e:
                results.append({
                    'permalink': permalink,
                    'success': False,
                    'error': str(e)
                })
        
        return jsonify({
            'total': len(results),
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': {
            'home': '/',
            'status': '/api/status',
            'product': '/api/product/<permalink>',
            'search': '/api/search?q=<query>',
            'batch': 'POST /api/batch/products'
        }
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': str(error)
    }), 500

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 Klikindomaret API Service Starting...")
    print("=" * 60)
    print("\n📡 Available at: http://localhost:5000")
    print("\n📚 Endpoints:")
    print("   • Home: http://localhost:5000")
    print("   • Status: http://localhost:5000/api/status")
    print("   • Product: http://localhost:5000/api/product/<permalink>")
    print("   • Search: http://localhost:5000/api/search?q=<query>")
    print("\n💡 Token auto-refresh is running in background")
    print("=" * 60 + "\n")
    
    # Run the app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Disable reloader to prevent token manager from starting twice
    )