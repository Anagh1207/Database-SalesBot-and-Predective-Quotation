from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.logger import get_logger

router = APIRouter(prefix="/predict", tags=["Prediction & BI"])
logger = get_logger("predict_router")


# ── REQUEST / RESPONSE MODELS ──────────────────────────────────────────────

class PredictRequest(BaseModel):
    prod_type: str = Field(..., example="CL - Cladding")
    job_type:  str = Field(..., example="Additional Product Sheet")
    est_hrs:   float = Field(default=40.0, ge=0)


class BIRequest(BaseModel):
    query_type: str = Field(..., example="customer_growth")
    top_n: int = Field(default=10, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = None


# ── PREDICTION ENDPOINTS ───────────────────────────────────────────────────

@router.post("/effort")
def predict_effort(req: PredictRequest):
    """
    Predicts effort in hours for a job.
    Returns point estimate + confidence interval + risk flag.
    """
    try:
        from predictor.predict import predict_effort as _predict
        result = _predict(req.prod_type, req.job_type, req.est_hrs)
        return result
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Model not trained yet. Run: python predictor/train.py"
        )
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similar-jobs")
def similar_jobs(req: PredictRequest):
    """
    Finds similar historical jobs.
    Returns table with est hrs, act hrs, variation.
    """
    try:
        from predictor.predict import find_similar_jobs
        jobs = find_similar_jobs(req.prod_type, req.job_type)
        return {"total": len(jobs), "jobs": jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/product-types")
def get_product_types():
    """Returns all known product types the model was trained on."""
    try:
        from predictor.predict import get_product_types
        return {"product_types": get_product_types()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job-types")
def get_job_types():
    """Returns all known job types."""
    try:
        from predictor.predict import get_job_types
        return {"job_types": get_job_types()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── BUSINESS INTELLIGENCE ENDPOINTS ───────────────────────────────────────

@router.get("/bi/customer-growth")
def bi_customer_growth(top_n: int = 10):
    """Top growing and declining customers YoY."""
    try:
        from predictor.bi_engine import customer_growth
        return customer_growth(top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bi/product-trends")
def bi_product_trends(top_n: int = 15):
    """Fastest growing and declining product types."""
    try:
        from predictor.bi_engine import product_trends
        return product_trends(top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bi/job-type-intelligence")
def bi_job_type_intelligence():
    """Revenue and volume by job type."""
    try:
        from predictor.bi_engine import job_type_intelligence
        return job_type_intelligence()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bi/salesperson-analysis")
def bi_salesperson_analysis():
    """Salesperson growth, diversification, and revenue per customer."""
    try:
        from predictor.bi_engine import salesperson_analysis
        return salesperson_analysis()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bi/cross-sell")
def bi_cross_sell(top_n: int = 15):
    """Customers buying from only one work stream — cross-sell targets."""
    try:
        from predictor.bi_engine import cross_sell_opportunities
        return cross_sell_opportunities(top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bi/target-achievement")
def bi_target_achievement():
    """Salesperson target achievement for current financial year."""
    try:
        from predictor.bi_engine import target_achievement
        return target_achievement()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bi/sales-summary")
def bi_sales_summary(
    sales_person:  Optional[str] = None,
    customer_code: Optional[str] = None,
    fin_year:      Optional[int] = None,
    product_type:  Optional[str] = None,
):
    """Flexible sales summary with optional filters."""
    try:
        from predictor.bi_engine import sales_summary
        return sales_summary(sales_person, customer_code, fin_year, product_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))