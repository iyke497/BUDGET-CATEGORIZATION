# fmoh2024/main/routes.py (alternative using ComplianceService)
from datetime import datetime, timedelta

from flask import render_template

from fmoh2024.main import bp
from fmoh2024.compliance.services import ComplianceService


@bp.route("/")
def index():
    """Home page route with dashboard overview."""
    
    fiscal_year = "2024"
    
    # Use the compliance service to get consistent stats
    summary = ComplianceService.get_summary_stats(fiscal_year)
    
    # Get all compliance data to calculate tier counts
    compliance_data = ComplianceService.get_all_compliance_stats(fiscal_year)
    
    # Calculate tier counts
    tier_counts = {"high": 0, "medium": 0, "low": 0, "zero": 0}
    for item in compliance_data:
        tier = item["status"]["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    # Get recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)

    recent_activities = []
    
    # You might want to add a method to ComplianceService for recent activity
    # For now, keep the sample activities

    return render_template(
        "main/index.html",
        total_projects=summary["total_projects"],
        categorized_projects=summary["total_categorized"],
        categorization_rate=summary["overall_compliance"],
        focus_agencies=summary["total_agencies"],
        compliance_rate=summary["overall_compliance"],
        tier_counts=tier_counts,
        recent_activities=recent_activities or [
            {
                "time": "2 days ago",
                "icon": "📊",
                "text": "Compliance dashboard updated",
            },
            {
                "time": "5 days ago",
                "icon": "📥",
                "text": f"Survey data import completed for FY {fiscal_year}",
            },
            {
                "time": "1 week ago",
                "icon": "🔍",
                "text": f"Matching process completed: {summary['total_categorized']} projects matched",
            },
        ],
        fiscal_year=fiscal_year,
    )