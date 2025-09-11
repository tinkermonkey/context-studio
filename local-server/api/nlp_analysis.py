"""
FastAPI router for NLP Analysis API endpoint.
"""

from fastapi import APIRouter, status, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from nlp.models import NLPAnalysisRequest, NLPErrorResponse, NLPSuccessResponse
from nlp.pipeline import get_pipeline
from nlp.processors import process_nlp_result
from nlp.proxy_manager import get_proxy_manager
from utils.logger import get_logger
from config import get_settings

logger = get_logger("nlp_analysis")

router = APIRouter()

settings = {
    "NLP_MAX_TEXT_LENGTH": 512
}

@router.post("/nlp_analysis", response_model=NLPSuccessResponse, responses={
    400: {"model": NLPErrorResponse},
    422: {"model": NLPErrorResponse},
    500: {"model": NLPErrorResponse},
})
async def nlp_analysis(request: Request):
    """
    Analyze text using NLP pipeline and return structured response.
    """
    try:
        body = await request.json()
        req = NLPAnalysisRequest(**body)
    except ValidationError as ve:
        logger.error(f"Validation error: {ve}")
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={
            "success": False,
            "error": "Invalid request format.",
            "details": ve.errors()
        })
    except Exception as e:
        logger.error(f"Malformed request: {e}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
            "success": False,
            "error": "Malformed request.",
            "details": str(e)
        })

    text = req.text
    if not text or len(text) == 0:
        logger.warning("Empty text submitted to NLP endpoint.")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
            "success": False,
            "error": "Text cannot be empty."
        })
    if len(text) > settings["NLP_MAX_TEXT_LENGTH"]:
        logger.warning(f"Text length {len(text)} exceeds max allowed {settings['NLP_MAX_TEXT_LENGTH']}.")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
            "success": False,
            "error": f"Text exceeds maximum length of {settings['NLP_MAX_TEXT_LENGTH']} characters."
        })

    try:
        pipeline = get_pipeline().get_nlp()
        if pipeline is None:
            raise RuntimeError("NLP pipeline is not initialized.")
        doc = pipeline(text)
        response_data = process_nlp_result(text, doc)
        return NLPSuccessResponse(success=True, data=response_data)
    except Exception as e:
        logger.error(f"NLP pipeline error: {e}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={
            "success": False,
            "error": "Internal server error during NLP analysis.",
            "details": str(e)
        })

@router.post("/nlp_analysis/proxy/configure")
async def configure_proxy(request: Request):
    """
    Update reference API proxy configuration and reload pipeline.
    """
    try:
        body = await request.json()
        
        # Validate configuration
        valid_apis = ["concepcy", "spacy_dbpedia_spotlight"]
        for api, enabled in body.items():
            if api not in valid_apis:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"Invalid API: {api}"}
                )
            if not isinstance(enabled, bool):
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"Value for {api} must be boolean"}
                )
        
        # Update settings
        settings = get_settings()
        settings.ENABLE_CACHING_PROXY.update(body)
        
        # Reload pipeline with new configuration
        pipeline = get_pipeline()
        if not pipeline.reload_pipeline():
            return JSONResponse(
                status_code=500,
                content={
                    "success": False, 
                    "error": "Failed to reload pipeline with new configuration"
                }
            )
        
        return JSONResponse(content={
            "success": True,
            "message": "Proxy configuration updated",
            "configuration": settings.ENABLE_CACHING_PROXY
        })
        
    except Exception as e:
        logger.error(f"Error updating proxy configuration: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/nlp_analysis/proxy/status")
async def get_proxy_status():
    """
    Get current proxy configuration and status.
    """
    try:
        settings = get_settings()
        proxy_manager = get_proxy_manager()
        
        return JSONResponse(content={
            "success": True,
            "proxy_enabled": proxy_manager.is_proxy_enabled(),
            "proxy_running": proxy_manager.is_running,
            "configuration": settings.ENABLE_CACHING_PROXY,
            "proxy_config": {
                "host": settings.REFERENCE_API_BUDDY_CONFIG["server"]["host"],
                "port": settings.REFERENCE_API_BUDDY_CONFIG["server"]["port"]
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting proxy status: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/nlp_analysis/proxy/monitor")
async def get_proxy_monitoring():
    """
    Get comprehensive monitoring statistics from the reference API buddy proxy.
    
    Returns cache stats, upstream performance, database health, proxy health,
    and throttling information when the proxy is running.
    """
    try:
        proxy_manager = get_proxy_manager()
        
        if not proxy_manager.is_running:
            return JSONResponse(content={
                "success": True,
                "proxy_running": False,
                "message": "Proxy is not currently running",
                "stats": None
            })
        
        stats = proxy_manager.get_monitoring_stats()
        
        if stats is None:
            return JSONResponse(content={
                "success": True,
                "proxy_running": True,
                "message": "Monitoring data not available",
                "stats": None
            })
        
        return JSONResponse(content={
            "success": True,
            "proxy_running": True,
            "stats": stats
        })
        
    except Exception as e:
        logger.error(f"Error getting proxy monitoring data: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
