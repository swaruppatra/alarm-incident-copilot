from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Report service liveness for readiness checks and orchestration.

    Args:
        None

    Returns:
        dict[str, str]: a simple status payload.
    """
    return {"status": "ok"}
