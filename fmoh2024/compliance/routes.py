# fmoh2024/compliance/routes.py
from flask import jsonify, render_template, request
from sqlalchemy import case, func

from fmoh2024.compliance import bp
from fmoh2024.compliance.services import ComplianceService
from fmoh2024.extensions import db
from fmoh2024.models import SurveyResponse, IntermediateOutcome, BudgetCategory, HealthCareService, SecondaryHealthService, TertiaryHealthService, PrimaryHealthService


@bp.route("/")
def dashboard():
    """Main compliance dashboard showing all agencies."""
    fiscal_year = request.args.get("fiscal_year", "2024")

    # Get compliance data
    compliance_data = ComplianceService.get_all_compliance_stats(fiscal_year)
    summary = ComplianceService.get_summary_stats(fiscal_year)

    return render_template(
        "compliance/dashboard.html",
        compliance_data=compliance_data,
        summary=summary,
        fiscal_year=fiscal_year,
    )


@bp.route("/agency/<int:agency_id>")
def agency_detail(agency_id):
    """Detailed view for a specific agency."""
    fiscal_year = request.args.get("fiscal_year", "2024")

    details = ComplianceService.get_agency_project_details(agency_id, fiscal_year)

    if not details:
        return "Agency not found", 404

    return render_template(
        "compliance/agency_detail.html", details=details, fiscal_year=fiscal_year
    )


@bp.route("/api/compliance")
def api_compliance():
    """API endpoint for compliance data (for charts/JS)."""
    fiscal_year = request.args.get("fiscal_year", "2024")
    compliance_data = ComplianceService.get_all_compliance_stats(fiscal_year)
    summary = ComplianceService.get_summary_stats(fiscal_year)

    return jsonify(
        {
            "summary": summary,
            "agencies": [
                {
                    "id": item["agency"].id,
                    "name": item["agency"].agency_name,
                    "ministry": item["agency"].ministry_name,
                    "code": item["agency"].agency_code,
                    "total_projects": item["total_projects"],
                    "categorized": item["categorized_projects"],
                    "compliance": item["compliance_percentage"],
                    "status": item["status"],
                }
                for item in compliance_data
            ],
        }
    )


# Add to fmoh2024/compliance/routes.py


@bp.route("/api/intermediate-outcome-distribution")
def api_intermediate_outcome_distribution():
    """API endpoint for intermediate outcome distribution"""
    fiscal_year = request.args.get("fiscal_year", "2024")

    # Query to count by intermediate_outcome
    outcomes = (
        db.session.query(
            SurveyResponse.intermediate_outcome, func.count().label("count")
        )
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.intermediate_outcome.isnot(None),
            SurveyResponse.intermediate_outcome != "",
        )
        .group_by(SurveyResponse.intermediate_outcome)
        .order_by(func.count().desc())
        .all()
    )

    # Process outcomes - take top 5, rest as "Other"
    labels = []
    values = []
    other_count = 0

    for i, (outcome, count) in enumerate(outcomes):
        if i < 5:  # Show top 5 outcomes
            # Clean up the outcome text
            clean_outcome = str(outcome).strip()
            # Split at '(' and take text before it
            label = clean_outcome.split("(")[0].strip()
            labels.append(label)
            values.append(count)
        else:
            other_count += count

    if other_count > 0:
        labels.append("Other Outcomes")
        values.append(other_count)

    return jsonify(
        {"labels": labels, "values": values, "total": sum(values) + other_count}
    )


@bp.route("/api/healthcare-service-distribution")
def api_healthcare_service_distribution():
    """API endpoint for healthcare service distribution using SurveyResponse.health_care_service"""
    fiscal_year = request.args.get("fiscal_year", "2024")

    # Query to count by health_care_service
    services = (
        db.session.query(
            SurveyResponse.health_care_service, func.count().label("count")
        )
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.health_care_service.isnot(None),
            SurveyResponse.health_care_service != "",
        )
        .group_by(SurveyResponse.health_care_service)
        .order_by(func.count().desc())
        .all()
    )

    # Process services - take top 5, rest as "Other"
    labels = []
    values = []
    other_count = 0

    for i, (service, count) in enumerate(services):
        if i < 5:  # Show top 5 services
            clean_service = str(service).strip()
            # Truncate if too long for display
            if len(clean_service) > 40:
                clean_service = clean_service[:40] + "..."
            labels.append(clean_service)
            values.append(count)
        else:
            other_count += count

    if other_count > 0:
        labels.append("Other Services")
        values.append(other_count)

    return jsonify(
        {"labels": labels, "values": values, "total": sum(values) + other_count}
    )


@bp.route("/api/category-distribution")
def api_category_distribution():
    """API endpoint for budget category distribution using SurveyResponse.category"""
    fiscal_year = request.args.get("fiscal_year", "2024")

    # Query to count by category
    categories = (
        db.session.query(SurveyResponse.category, func.count().label("count"))
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.category.isnot(None),
            SurveyResponse.category != "",
        )
        .group_by(SurveyResponse.category)
        .order_by(func.count().desc())
        .all()
    )

    # Process categories - take top 5, rest as "Other"
    labels = []
    values = []
    other_count = 0

    for i, (category, count) in enumerate(categories):
        if i < 5:  # Show top 5 categories
            clean_category = str(category).strip()
            labels.append(clean_category)
            values.append(count)
        else:
            other_count += count

    if other_count > 0:
        labels.append("Other Categories")
        values.append(other_count)

    return jsonify(
        {"labels": labels, "values": values, "total": sum(values) + other_count}
    )


@bp.route("/api/service-level-breakdown")
def api_service_level_breakdown():
    """API endpoint for detailed service level breakdown with subcategories"""
    fiscal_year = request.args.get("fiscal_year", "2024")

    # Get detailed breakdown of primary health care services
    primary_services = (
        db.session.query(
            SurveyResponse.primary_health_care, func.count().label("count")
        )
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.primary_health_care.isnot(None),
        )
        .group_by(SurveyResponse.primary_health_care)
        .order_by(func.count().desc())
        .limit(5)
        .all()
    )

    # Get detailed breakdown of secondary health care services
    secondary_services = (
        db.session.query(
            SurveyResponse.secondary_health_care, func.count().label("count")
        )
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.secondary_health_care.isnot(None),
        )
        .group_by(SurveyResponse.secondary_health_care)
        .order_by(func.count().desc())
        .limit(5)
        .all()
    )

    # Get detailed breakdown of tertiary health care services
    tertiary_services = (
        db.session.query(
            SurveyResponse.tertiary_health_care, func.count().label("count")
        )
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.tertiary_health_care.isnot(None),
        )
        .group_by(SurveyResponse.tertiary_health_care)
        .order_by(func.count().desc())
        .limit(5)
        .all()
    )

    return jsonify(
        {
            "primary": [
                {"service": s or "Unspecified", "count": c} for s, c in primary_services
            ],
            "secondary": [
                {"service": s or "Unspecified", "count": c}
                for s, c in secondary_services
            ],
            "tertiary": [
                {"service": s or "Unspecified", "count": c}
                for s, c in tertiary_services
            ],
        }
    )


# Add to fmoh2024/compliance/routes.py


@bp.route("/api/dashboard-stats")
def api_dashboard_stats():
    """Consolidated API endpoint for all dashboard statistics"""
    fiscal_year = request.args.get("fiscal_year", "2024")

    # Get compliance summary
    summary = ComplianceService.get_summary_stats(fiscal_year)

    # Get compliance data for agencies
    compliance_data = ComplianceService.get_all_compliance_stats(fiscal_year)

    # Get intermediate outcome distribution
    outcomes = (
        db.session.query(
            SurveyResponse.intermediate_outcome, func.count().label("count")
        )
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.intermediate_outcome.isnot(None),
            SurveyResponse.intermediate_outcome != "",
        )
        .group_by(SurveyResponse.intermediate_outcome)
        .order_by(func.count().desc())
        .limit(6)
        .all()
    )  # Get top 6 to allow for "Other" category

    outcome_labels = []
    outcome_values = []
    for outcome, count in outcomes:
        # Use the enum's display method
        display_value = IntermediateOutcome.get_display_value(outcome)
        # Extract just the readable part (before the parenthesis)
        if '(' in display_value:
            display_value = display_value.split('(')[0].strip()
        outcome_labels.append(display_value)
        outcome_values.append(count)

    # Get category distribution
    categories = (
        db.session.query(SurveyResponse.category, func.count().label("count"))
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.category.isnot(None),
        )
        .group_by(SurveyResponse.category)
        .order_by(func.count().desc())
        .limit(6)
        .all()
    )

    category_labels = []
    category_values = []
    for category, count in categories:
        # Use the enum's display method
        display_value = BudgetCategory.get_display_value(category)
        # Extract just the readable part (before the parenthesis)
        if '(' in display_value:
            display_value = display_value.split('(')[0].strip()
        category_labels.append(display_value)
        category_values.append(count)

    # Get healthcare service distribution
    services = (
        db.session.query(
            SurveyResponse.health_care_service, func.count().label("count")
        )
        .filter(
            SurveyResponse.fiscal_year == fiscal_year,
            SurveyResponse.is_matched == True,
            SurveyResponse.health_care_service.isnot(None),
        )
        .group_by(SurveyResponse.health_care_service)
        .order_by(func.count().desc())
        .limit(6)
        .all()
    )

    service_labels = []
    service_values = []
    for service, count in services:
        # Use the enum's display method
        display_value = HealthCareService.get_display_value(service)
        service_labels.append(display_value)
        service_values.append(count)

    # Calculate tier distribution for compliance chart
    tier_counts = {"high": 0, "medium": 0, "low": 0, "zero": 0}
    for item in compliance_data:
        tier = item["status"]["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    return jsonify(
        {
            "summary": {
                "total_agencies": summary["total_agencies"],
                "total_projects": summary["total_projects"],
                "total_categorized": summary["total_categorized"],
                "overall_compliance": summary["overall_compliance"],
                "focus_agencies": summary["total_agencies"],
            },
            "compliance_distribution": {
                "labels": [
                    "High Compliance (≥80%)",
                    "Medium Compliance (50-79%)",
                    "Low Compliance (1-49%)",
                    "No Compliance (0%)",
                ],
                "values": [
                    tier_counts["high"],
                    tier_counts["medium"],
                    tier_counts["low"],
                    tier_counts["zero"],
                ],
                "colors": ["#4baa73", "#f39c12", "#e67e22", "#b91c1c"],
            },
            "intermediate_outcome_distribution": {
                "labels": outcome_labels,
                "values": outcome_values,
                "title": "Intermediate Outcomes",
            },
            "category_distribution": {
                "labels": category_labels,
                "values": category_values,
                "title": "Budget Categories",
            },
            "healthcare_service_distribution": {
                "labels": service_labels,
                "values": service_values,
                "title": "Healthcare Services",
            },
        }
    )
