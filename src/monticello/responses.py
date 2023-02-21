from starlette import responses

qme_responses = {
    200: {
        "description": "quantized mesh",
        "content": {
            "application/vnd.quantized-mesh" : {},
        }
    }
}

class QMEResponse(responses.Response):
    """
    """  
    media_type = "application/vnd.quantized-mesh"
