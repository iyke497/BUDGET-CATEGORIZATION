# fmoh2024/compliance/services.py
from datetime import datetime

from sqlalchemy import case, func

from fmoh2024.extensions import db, cache
from fmoh2024.models import MinistryAgency, Project, SurveyResponse


class ComplianceService:
    """Service layer for compliance calculations and business logic."""

    # Agencies with codes starting with 521 are the focus
    FOCUS_AGENCY_PREFIX = "521"

    @classmethod
    def get_focus_agencies(cls, fiscal_year="2024"):
        """Get all agencies with codes starting with 521."""
        return (
            MinistryAgency.query.filter(
                MinistryAgency.agency_code.startswith(cls.FOCUS_AGENCY_PREFIX),
                MinistryAgency.fiscal_year == fiscal_year,
                MinistryAgency.is_active == True,
            )
            .order_by(MinistryAgency.ministry_name, MinistryAgency.agency_name)
            .all()
        )

    @classmethod
    def calculate_agency_compliance(cls, agency_id, fiscal_year="2024"):
        """
        Calculate compliance for a single agency.
        Compliance = (Categorized Projects / Total Projects) * 100
        """
        agency = MinistryAgency.query.get(agency_id)
        if not agency:
            return None

        # Get all projects for this agency
        total_projects = Project.query.filter_by(agency_id=agency_id).count()

        # Get categorized projects (those with matched survey responses)
        categorized_projects = (
            db.session.query(Project)
            .join(SurveyResponse, Project.id == SurveyResponse.project_id)
            .filter(
                Project.agency_id == agency_id,
                SurveyResponse.is_matched == True,
                SurveyResponse.fiscal_year == fiscal_year,
            )
            .count()
        )

        # Calculate compliance percentage
        if total_projects > 0:
            compliance_percentage = (categorized_projects / total_projects) * 100
        else:
            compliance_percentage = 0.0

        return {
            "agency": agency,
            "total_projects": total_projects,
            "categorized_projects": categorized_projects,
            "compliance_percentage": round(compliance_percentage, 2),
            "status": cls._get_compliance_status(compliance_percentage),
        }

    @classmethod
    @cache.memoize(timeout=300)
    def get_all_compliance_stats(cls, fiscal_year="2024"):
        """
        Get compliance statistics for all focus agencies.
        Returns list of agencies with their compliance data.
        """
        agencies = cls.get_focus_agencies(fiscal_year)

        compliance_data = []
        for agency in agencies:
            stats = cls.calculate_agency_compliance(agency.id, fiscal_year)
            if stats:
                compliance_data.append(stats)

        # Sort by compliance percentage (lowest first - those needing attention)
        compliance_data.sort(key=lambda x: x["compliance_percentage"])

        return compliance_data

    @classmethod
    @cache.memoize(timeout=300)
    def get_summary_stats(cls, fiscal_year="2024"):
        """Get overall compliance summary statistics."""
        agencies = cls.get_focus_agencies(fiscal_year)

        total_agencies = len(agencies)
        total_projects = 0
        total_categorized = 0

        for agency in agencies:
            stats = cls.calculate_agency_compliance(agency.id, fiscal_year)
            if stats:
                total_projects += stats["total_projects"]
                total_categorized += stats["categorized_projects"]

        overall_compliance = (
            (total_categorized / total_projects * 100) if total_projects > 0 else 0
        )

        # Count agencies by compliance tier
        tiers = {
            "high": 0,  # >= 80%
            "medium": 0,  # 50-79%
            "low": 0,  # < 50%
            "zero": 0,  # 0%
        }

        for agency in agencies:
            stats = cls.calculate_agency_compliance(agency.id, fiscal_year)
            if stats:
                status = stats["status"]
                tiers[status["tier"]] += 1

        return {
            "total_agencies": total_agencies,
            "total_projects": total_projects,
            "total_categorized": total_categorized,
            "overall_compliance": round(overall_compliance, 2),
            "tiers": tiers,
            "fiscal_year": fiscal_year,
            "as_at": datetime.utcnow(),
        }

    @classmethod
    def get_agency_project_details(cls, agency_id, fiscal_year="2024"):
        """Get detailed project list for an agency with categorization status."""
        agency = MinistryAgency.query.get(agency_id)
        if not agency:
            return None

        # Get all projects with their latest survey response
        projects = (
            db.session.query(Project, SurveyResponse)
            .outerjoin(
                SurveyResponse,
                (Project.id == SurveyResponse.project_id)
                & (SurveyResponse.is_matched == True)
                & (SurveyResponse.fiscal_year == fiscal_year),
            )
            .filter(Project.agency_id == agency_id)
            .all()
        )

        project_details = []
        for project, response in projects:
            project_details.append(
                {
                    "id": project.id,
                    "code": project.code,
                    "name": project.project_name,
                    "appropriation": (
                        float(project.appropriation) if project.appropriation else 0
                    ),
                    "status": project.project_status,
                    "is_categorized": response is not None,
                    "categorization": (
                        {
                            "category": response.category if response else None,
                            "health_service": (
                                response.health_care_service if response else None
                            ),
                            "primary_care": (
                                response.primary_health_care if response else None
                            ),
                            "secondary_care": (
                                response.secondary_health_care if response else None
                            ),
                            "tertiary_care": (
                                response.tertiary_health_care if response else None
                            ),
                        }
                        if response
                        else None
                    ),
                }
            )

        return {
            "agency": agency,
            "total_projects": len(project_details),
            "categorized_count": sum(1 for p in project_details if p["is_categorized"]),
            "uncategorized_count": sum(
                1 for p in project_details if not p["is_categorized"]
            ),
            "projects": project_details,
            "compliance": cls.calculate_agency_compliance(agency_id, fiscal_year),
        }

    @staticmethod
    def _get_compliance_status(percentage):
        """Determine compliance status based on percentage."""
        if percentage >= 80:
            return {
                "label": "High Compliance",
                "tier": "high",
                "color": "green",
                "icon": "✅",
            }
        elif percentage >= 50:
            return {
                "label": "Medium Compliance",
                "tier": "medium",
                "color": "yellow",
                "icon": "⚠️",
            }
        elif percentage > 0:
            return {
                "label": "Low Compliance",
                "tier": "low",
                "color": "orange",
                "icon": "🔴",
            }
        else:
            return {
                "label": "No Compliance",
                "tier": "zero",
                "color": "red",
                "icon": "❌",
            }
