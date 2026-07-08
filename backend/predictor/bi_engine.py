"""
Business Intelligence Engine.
Answers the 5 high-value queries from the Top_5_Areas document.

1. Customer growth / decline
2. Product trends
3. Job type intelligence
4. Salesperson analysis
5. Cross-sell opportunities
"""

import sqlite3
import pandas as pd
from typing import Dict, Any, List
from app.config import settings
from app.logger import get_logger

logger = get_logger("bi_engine")
DB_PATH = settings.DB_PATH


def get_connection(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── QUERY 1: CUSTOMER GROWTH / DECLINE ────────────────────────────────────

def customer_growth(
    top_n: int = 10,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Shows customer revenue ranking with growth trend.
    Uses H1 vs H2 of the most-populated financial year for trend direction
    since FY2026 is a partial year and cross-year YoY comparisons are
    misleading. H1 = Jul–Dec, H2 = Jan–Jun.
    """
    conn = get_connection(db_path)

    # Use the most-populated year as the reliable full year (FY2025)
    current_fy = conn.execute("""
        SELECT fin_year FROM sales
        GROUP BY fin_year
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """).fetchone()[0]

    rows = conn.execute("""
        WITH half_year AS (
            SELECT
                customer_code,
                CASE
                    WHEN CAST(strftime('%m', sale_date) AS INTEGER) >= 7 THEN 'H1'
                    ELSE 'H2'
                END AS half,
                SUM(contract_price) AS revenue,
                COUNT(*)            AS jobs
            FROM sales
            WHERE fin_year = ?
            GROUP BY customer_code, half
        ),
        pivoted AS (
            SELECT
                COALESCE(h1.customer_code, h2.customer_code) AS customer_code,
                COALESCE(h1.revenue, 0) AS h1_rev,
                COALESCE(h2.revenue, 0) AS h2_rev,
                COALESCE(h1.jobs, 0)    AS h1_jobs,
                COALESCE(h2.jobs, 0)    AS h2_jobs,
                COALESCE(h1.revenue, 0) + COALESCE(h2.revenue, 0) AS total_rev
            FROM (SELECT * FROM half_year WHERE half = 'H1') h1
            LEFT JOIN (SELECT * FROM half_year WHERE half = 'H2') h2
                ON h1.customer_code = h2.customer_code
        ),
        with_trend AS (
            SELECT *,
                ROUND(
                    CASE
                        WHEN h1_rev > 0
                        THEN ((h2_rev - h1_rev) / h1_rev) * 100
                        ELSE 0
                    END
                , 1) AS half_year_growth,
                CASE
                    WHEN h2_rev > h1_rev * 1.1  THEN 'Growing'
                    WHEN h2_rev = 0             THEN 'At Risk'
                    WHEN h2_rev < h1_rev * 0.9  THEN 'Declining'
                    ELSE                             'Stable'
                END AS trend
            FROM pivoted
        )
        SELECT * FROM with_trend
        ORDER BY total_rev DESC
        LIMIT ?
    """, (current_fy, top_n)).fetchall()

    # Stopped buying — active in the full year but nothing since
    stopped = conn.execute("""
        SELECT DISTINCT customer_code
        FROM sales
        WHERE fin_year = ?
          AND customer_code NOT IN (
              SELECT DISTINCT customer_code
              FROM sales
              WHERE fin_year > ?
          )
        LIMIT 5
    """, (current_fy, current_fy)).fetchall()

    conn.close()
    results = [dict(r) for r in rows]
    stopped_list = [r["customer_code"] for r in stopped]

    growing   = sum(1 for r in results if r["trend"] == "Growing")
    stable    = sum(1 for r in results if r["trend"] == "Stable")
    declining = sum(1 for r in results if r["trend"] == "Declining")
    at_risk   = sum(1 for r in results if r["trend"] == "At Risk")

    logger.info(f"Customer growth — {len(results)} customers analysed")
    return {
        "query_type":     "customer_growth",
        "total":          len(results),
        "results":        results,
        "stopped_buying": stopped_list,
        "summary": {
            "growing": growing, "stable": stable,
            "declining": declining, "at_risk": at_risk,
        },
        "note": f"Trend based on H1 (Jul–Dec) vs H2 (Jan–Jun) within FY{current_fy} — the most recent complete financial year.",
    }



# ── QUERY 2: PRODUCT TRENDS ────────────────────────────────────────────────

def product_trends(
    top_n: int = 15,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Shows fastest growing and declining product types by revenue.
    """
    conn = get_connection(db_path)

    rows = conn.execute("""
        WITH yearly AS (
            SELECT
                product_type,
                fin_year,
                SUM(contract_price) AS revenue,
                COUNT(*)            AS job_count
            FROM sales
            WHERE fin_year IN (
                SELECT DISTINCT fin_year FROM sales
                ORDER BY fin_year DESC LIMIT 2
            )
            GROUP BY product_type, fin_year
        ),
        pivoted AS (
            SELECT
                a.product_type,
                a.revenue                                        AS current_rev,
                COALESCE(b.revenue, 0)                          AS prev_rev,
                a.job_count                                      AS current_jobs,
                ROUND(
                    CASE WHEN COALESCE(b.revenue, 0) > 0
                    THEN ((a.revenue - b.revenue) / b.revenue) * 100
                    ELSE 100 END
                , 1)                                             AS yoy_growth_pct
            FROM yearly a
            LEFT JOIN yearly b
                ON a.product_type = b.product_type
               AND b.fin_year = a.fin_year - 1
            WHERE a.fin_year = (SELECT MAX(fin_year) FROM sales)
        )
        SELECT *,
            CASE
                WHEN yoy_growth_pct >= 30  THEN 'Hot'
                WHEN yoy_growth_pct >= 0   THEN 'Growing'
                WHEN yoy_growth_pct >= -20 THEN 'Slowing'
                ELSE 'Declining'
            END AS trend
        FROM pivoted
        WHERE product_type != 'xx'
          AND product_type != ''
        ORDER BY current_rev DESC
        LIMIT ?
    """, (top_n,)).fetchall()

    conn.close()
    results = [dict(r) for r in rows]
    logger.info(f"Product trends query — {len(results)} products")
    return {
        "query_type": "product_trends",
        "total": len(results),
        "results": results,
    }


# ── QUERY 3: JOB TYPE INTELLIGENCE ────────────────────────────────────────

def job_type_intelligence(
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Revenue and volume by job type.
    Identifies hot sectors and declining areas.
    """
    conn = get_connection(db_path)

    rows = conn.execute("""
        WITH yearly AS (
            SELECT
                job_type,
                fin_year,
                SUM(contract_price)  AS revenue,
                COUNT(*)             AS job_count,
                AVG(contract_price)  AS avg_price
            FROM sales
            WHERE fin_year IN (
                SELECT DISTINCT fin_year FROM sales
                ORDER BY fin_year DESC LIMIT 2
            )
            GROUP BY job_type, fin_year
        ),
        pivoted AS (
            SELECT
                a.job_type,
                ROUND(a.revenue, 2)                              AS current_rev,
                COALESCE(ROUND(b.revenue, 2), 0)                AS prev_rev,
                a.job_count                                      AS current_jobs,
                ROUND(a.avg_price, 2)                           AS avg_price,
                ROUND(
                    CASE WHEN COALESCE(b.revenue, 0) > 0
                    THEN ((a.revenue - b.revenue) / b.revenue) * 100
                    ELSE 100 END
                , 1)                                             AS yoy_growth_pct
            FROM yearly a
            LEFT JOIN yearly b
                ON a.job_type = b.job_type
               AND b.fin_year = a.fin_year - 1
            WHERE a.fin_year = (SELECT MAX(fin_year) FROM sales)
        )
        SELECT * FROM pivoted
        ORDER BY current_rev DESC
    """).fetchall()

    conn.close()
    results = [dict(r) for r in rows]
    logger.info(f"Job type intelligence — {len(results)} job types")
    return {
        "query_type": "job_type_intelligence",
        "total": len(results),
        "results": results,
    }


# ── QUERY 4: SALESPERSON ANALYSIS ─────────────────────────────────────────

def salesperson_analysis(
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Shows each salesperson's performance across the two financial years
    in the database.

    Uses the most-populated year as the 'full year' baseline (FY2025)
    and the latest year as 'current YTD' (FY2026).

    Salespeople with zero revenue in the full year are flagged as 'New'.
    Salespeople with revenue in the full year but zero in the current
    year are flagged as 'Gone' — left or reassigned.

    Avoids showing a misleading YoY% because FY2026 is a partial year.
    """
    conn = get_connection(db_path)

    rows = conn.execute("""
        WITH full_year AS (
            -- Most-populated year = the reliable full year
            SELECT fin_year AS fy
            FROM sales
            GROUP BY fin_year
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ),
        current_year AS (
            SELECT MAX(fin_year) AS fy FROM sales
        ),
        sp_full AS (
            SELECT
                sales_person,
                ROUND(SUM(contract_price), 2)          AS full_rev,
                COUNT(DISTINCT customer_code)           AS full_customers,
                COUNT(DISTINCT product_type)            AS full_products,
                COUNT(*)                                AS full_jobs
            FROM sales
            WHERE fin_year = (SELECT fy FROM full_year)
              AND sales_person IS NOT NULL AND sales_person != ''
            GROUP BY sales_person
        ),
        sp_current AS (
            SELECT
                sales_person,
                ROUND(SUM(contract_price), 2)          AS current_rev,
                COUNT(DISTINCT customer_code)           AS current_customers,
                COUNT(*)                                AS current_jobs
            FROM sales
            WHERE fin_year = (SELECT fy FROM current_year)
              AND sales_person IS NOT NULL AND sales_person != ''
            GROUP BY sales_person
        ),
        combined AS (
            SELECT
                COALESCE(f.sales_person, c.sales_person) AS sales_person,
                COALESCE(f.full_rev, 0)                  AS full_rev,
                COALESCE(f.full_customers, 0)            AS full_customers,
                COALESCE(f.full_products, 0)             AS full_products,
                COALESCE(f.full_jobs, 0)                 AS full_jobs,
                COALESCE(c.current_rev, 0)               AS current_rev,
                COALESCE(c.current_customers, 0)         AS current_customers,
                COALESCE(c.current_jobs, 0)              AS current_jobs,
                ROUND(
                    COALESCE(c.current_rev, 0) /
                    NULLIF(COALESCE(c.current_customers, 0), 0)
                , 2)                                     AS rev_per_customer,
                CASE
                    WHEN COALESCE(f.full_rev, 0) = 0
                         AND COALESCE(c.current_rev, 0) > 0  THEN 'New'
                    WHEN COALESCE(f.full_rev, 0) > 0
                         AND COALESCE(c.current_rev, 0) = 0  THEN 'Gone'
                    ELSE 'Active'
                END AS status
            FROM sp_full f
            FULL OUTER JOIN sp_current c
                ON f.sales_person = c.sales_person
        )
        SELECT * FROM combined
        ORDER BY full_rev DESC
    """).fetchall()

    conn.close()
    results = [dict(r) for r in rows]
    logger.info(f"Salesperson analysis — {len(results)} salespeople")
    return {
        "query_type": "salesperson_analysis",
        "total":      len(results),
        "results":    results,
        "note":       "full_rev = FY2025 (complete year). current_rev = FY2026 YTD. No YoY% shown as FY2026 is a partial year.",
    }


# ── QUERY 5: CROSS-SELL OPPORTUNITIES ─────────────────────────────────────

def cross_sell_opportunities(
    top_n: int = 15,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Finds customers buying from only one work stream or narrow product range.
    These are the best cross-sell targets.
    """
    conn = get_connection(db_path)

    rows = conn.execute("""
        SELECT
            customer_code,
            COUNT(DISTINCT work_stream)   AS work_streams_used,
            COUNT(DISTINCT product_type)  AS products_used,
            COUNT(DISTINCT job_type)      AS job_types_used,
            ROUND(SUM(contract_price), 2) AS total_revenue,
            COUNT(*)                      AS total_jobs,
            GROUP_CONCAT(DISTINCT work_stream) AS work_streams_list
        FROM sales
        GROUP BY customer_code
        HAVING COUNT(DISTINCT work_stream) = 1
           AND COUNT(*) >= 3
        ORDER BY total_revenue DESC
        LIMIT ?
    """, (top_n,)).fetchall()

    conn.close()
    results = [dict(r) for r in rows]
    logger.info(f"Cross-sell opportunities — {len(results)} customers")
    return {
        "query_type": "cross_sell_opportunities",
        "total": len(results),
        "results": results,
        "insight": f"{len(results)} high-value customers buying from only one work stream — strong cross-sell potential",
    }


# ── GENERAL SALES QUERY ────────────────────────────────────────────────────

def sales_summary(
    sales_person: str = None,
    customer_code: str = None,
    fin_year: int = None,
    product_type: str = None,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Flexible sales summary with optional filters.
    Used for general queries like 'sales for SP1 this year'.
    """
    conn = get_connection(db_path)

    where_clauses = []
    params = []

    if sales_person:
        where_clauses.append("sales_person = ?")
        params.append(sales_person)
    if customer_code:
        where_clauses.append("customer_code = ?")
        params.append(customer_code)
    if fin_year:
        where_clauses.append("fin_year = ?")
        params.append(fin_year)
    if product_type:
        where_clauses.append("product_type LIKE ?")
        params.append(f"%{product_type}%")

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    row = conn.execute(f"""
        SELECT
            COUNT(*)                      AS total_jobs,
            ROUND(SUM(contract_price), 2) AS total_revenue,
            ROUND(AVG(contract_price), 2) AS avg_job_value,
            COUNT(DISTINCT customer_code) AS unique_customers,
            COUNT(DISTINCT product_type)  AS unique_products,
            MIN(sale_date)                AS first_sale,
            MAX(sale_date)                AS last_sale
        FROM sales
        {where_sql}
    """, params).fetchone()

    # Top customers
    top_customers = conn.execute(f"""
        SELECT
            customer_code,
            ROUND(SUM(contract_price), 2) AS revenue,
            COUNT(*) AS jobs
        FROM sales
        {where_sql}
        GROUP BY customer_code
        ORDER BY revenue DESC
        LIMIT 5
    """, params).fetchall()

    conn.close()

    return {
        "query_type": "sales_summary",
        "filters": {
            "sales_person":  sales_person,
            "customer_code": customer_code,
            "fin_year":      fin_year,
            "product_type":  product_type,
        },
        "summary": dict(row) if row else {},
        "top_customers": [dict(r) for r in top_customers],
    }


# ── TARGET ACHIEVEMENT ─────────────────────────────────────────────────────

def target_achievement(
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Calculates each salesperson's revenue and target achievement.
    Target is defined as average revenue across all salespeople
    for the current financial year.
    """
    conn = get_connection(db_path)

    rows = conn.execute("""
        SELECT
            sales_person,
            ROUND(SUM(contract_price), 2) AS revenue,
            COUNT(*)                      AS total_jobs,
            COUNT(DISTINCT customer_code) AS customers,
            fin_year
        FROM sales
        WHERE fin_year = (SELECT MAX(fin_year) FROM sales)
          AND sales_person IS NOT NULL
          AND sales_person != ''
        GROUP BY sales_person
        ORDER BY revenue DESC
    """).fetchall()

    conn.close()
    results = [dict(r) for r in rows]

    if not results:
        return {"query_type": "target_achievement", "results": []}

    # Calculate target as average revenue
    avg_rev = sum(r["revenue"] for r in results) / len(results)

    for r in results:
        r["target"]      = round(avg_rev, 2)
        r["achievement"] = round((r["revenue"] / avg_rev) * 100, 1)
        r["met_target"]  = r["achievement"] >= 100

    logger.info(f"Target achievement — {len(results)} salespeople")
    return {
        "query_type":   "target_achievement",
        "avg_target":   round(avg_rev, 2),
        "total":        len(results),
        "met_target":   sum(1 for r in results if r["met_target"]),
        "results":      results,
    }