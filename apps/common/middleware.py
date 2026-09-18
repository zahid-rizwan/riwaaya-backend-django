import json
from django.http import JsonResponse

class ResponseFormatMiddleware:
    """
    Middleware to format all successful JSON responses under /api/v1/ 
    into a standardized structure: {"success": true, "data": ..., "error": null}.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Apply standard formatting only to API endpoints, skipping schema docs
        if request.path.startswith('/api/v1/') and not request.path.startswith('/api/v1/schema/'):
            content_type = response.get('Content-Type', '')
            if response.status_code < 400 and 'application/json' in content_type:
                try:
                    # Retrieve the original JSON payload
                    content = response.content.decode('utf-8')
                    data = json.loads(content)
                    
                    # Avoid double-wrapping if already structured
                    if isinstance(data, dict) and ('success' in data or 'error' in data):
                        return response
                        
                    formatted_data = {
                        "success": True,
                        "data": data,
                        "error": None
                    }
                    
                    # Re-serialize and update response content
                    response.content = json.dumps(formatted_data).encode('utf-8')
                    response['Content-Length'] = str(len(response.content))
                except Exception:
                    # Fallback to original response in case of decoding errors
                    pass
                    
        return response
