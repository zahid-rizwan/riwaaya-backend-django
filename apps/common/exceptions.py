from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    # Call DRF's default exception handler first to get the standard error response.
    response = exception_handler(exc, context)

    if response is not None:
        # Standardize the error payload
        custom_data = {
            "success": False,
            "data": None,
            "error": {
                "code": getattr(exc, "default_code", "error"),
                "message": "",
                "details": None
            }
        }

        # Retrieve the detail message
        detail = response.data
        if isinstance(detail, dict):
            # Often field-level validation errors
            if "detail" in detail:
                custom_data["error"]["message"] = str(detail["detail"])
                custom_data["error"]["details"] = detail
            else:
                custom_data["error"]["message"] = "Validation failed."
                custom_data["error"]["details"] = detail
        elif isinstance(detail, list):
            custom_data["error"]["message"] = str(detail[0]) if detail else "An error occurred."
            custom_data["error"]["details"] = detail
        else:
            custom_data["error"]["message"] = str(detail)

        response.data = custom_data
    else:
        # Log unhandled exceptions (e.g., Database errors, syntax errors)
        logger.exception("Unhandled server exception", exc_info=exc)
        
        # In production, we don't want to expose raw traceback/error messages
        # But in local dev we can display them.
        from django.conf import settings
        message = str(exc) if settings.DEBUG else "An internal server error occurred."
        
        response = Response(
            {
                "success": False,
                "data": None,
                "error": {
                    "code": "server_error",
                    "message": message,
                    "details": None
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response
