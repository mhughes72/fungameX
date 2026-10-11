from contextlib import contextmanager

from fastapi import HTTPException

from ..services.llm import LLMError
from ..services.pipeline import BudgetExceeded, PipelineError


@contextmanager
def pipeline_errors():
    try:
        yield
    except BudgetExceeded as e:
        raise HTTPException(429, str(e))
    except PipelineError as e:
        raise HTTPException(400, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))
