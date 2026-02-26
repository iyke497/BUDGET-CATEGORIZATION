# fmoh2024/projects/services.py
from fmoh2024.models import Project, SurveyResponse, IntermediateOutcome, BudgetCategory, HealthCareService, PrimaryHealthService, SecondaryHealthService, TertiaryHealthService
from fmoh2024.extensions import db
from sqlalchemy import func, desc, or_, and_


def sanitize_value(value):
    """
    Sanitize a value to treat 'nan' strings as None.
    
    Handles cases where pandas/numpy exports resulted in string 'nan' values
    instead of proper NULL values in the database.
    
    Args:
        value: The value to sanitize
        
    Returns:
        None if value is 'nan' (case insensitive) or empty string, otherwise the value
    """
    if value is None:
        return None
    
    # Handle string values
    if isinstance(value, str):
        # Strip whitespace
        value = value.strip()
        
        # Check for 'nan' (case insensitive)
        if value.lower() == 'nan':
            return None
        
        # Check for empty string
        if value == '':
            return None
    
    return value


def format_enum_for_display(enum_value):
    """
    Format an enum value for frontend display.
    Returns the enum value (not the display text) for filtering.
    """
    if enum_value is None:
        return None
    
    # If it's already a string, return as-is
    if isinstance(enum_value, str):
        return enum_value
    
    # If it's an enum, return its value
    return enum_value.value if hasattr(enum_value, 'value') else str(enum_value)



class ProjectsService:
    """Service layer for project-related queries."""

    @staticmethod
    def get_all_projects(fiscal_year=None):
        """Return a list of Project objects for the given fiscal year.
        
        Filters projects to agencies with agency_code starting with '521'.
        """
        query = Project.query.filter(
            Project.agency_code.isnot(None),
            Project.agency_code.like('521%')  # Using like instead of startswith for better SQL compatibility
        )

        return query.order_by(Project.project_name).all()

    @staticmethod
    def get_project_by_id(project_id, fiscal_year=None):
        """Get a single project by ID."""
        return Project.query.filter_by(id=project_id).first()

    @staticmethod
    def get_projects_table_rows(fiscal_year=None):
        """Return a list of dicts with fields prepared for table display.

        Fields: code, project_name, agency (agency_name), health_care_service,
        intermediate_outcome, category, service_detail, appropriation, id.
        
        service_detail is chosen from primary/secondary/tertiary based on which
        of those fields is present on the most recent matched SurveyResponse.
        
        Enum values are returned as their string values for filtering.
        """
        projects = ProjectsService.get_all_projects(fiscal_year)
        rows = []

        for proj in projects:
            # Try to get most recent matched survey categorization
            survey = proj.get_categorization()

            health_service = None
            intermediate = None
            category = None
            service_detail = None

            if survey:
                # Format enum values for frontend
                health_service = format_enum_for_display(survey.health_care_service)
                intermediate = format_enum_for_display(survey.intermediate_outcome)
                category = format_enum_for_display(survey.category)

                # Intelligently select service_detail based on health_care_service level
                if health_service:
                    health_service_lower = health_service.lower()
                    if 'tertiary' in health_service_lower:
                        service_detail = format_enum_for_display(survey.tertiary_health_care)
                    elif 'secondary' in health_service_lower:
                        service_detail = format_enum_for_display(survey.secondary_health_care)
                    elif 'primary' in health_service_lower:
                        service_detail = format_enum_for_display(survey.primary_health_care)
                    else:
                        # Fallback: try all in order if health_care_service doesn't match
                        service_detail = (format_enum_for_display(survey.primary_health_care) or 
                                        format_enum_for_display(survey.secondary_health_care) or 
                                        format_enum_for_display(survey.tertiary_health_care))
                else:
                    # No health_care_service specified, use priority order
                    service_detail = (format_enum_for_display(survey.primary_health_care) or 
                                    format_enum_for_display(survey.secondary_health_care) or 
                                    format_enum_for_display(survey.tertiary_health_care))

            rows.append({
                'code': proj.code,
                'project_name': proj.project_name,
                'agency': proj.agency_name or proj.agency_code,
                'health_care_service': health_service,
                'intermediate_outcome': intermediate,
                'category': category,
                'service_detail': service_detail,
                'appropriation': float(proj.appropriation) if proj.appropriation is not None else None,
                'id': proj.id,
            })

        return rows

    @staticmethod
    def get_projects_page(start=0, length=10, sort_by=None, sort_dir='asc', filters=None, fiscal_year=None):
        """Return paginated projects with optional sorting and filters.

        Args:
            start: Zero-based offset for pagination
            length: Number of records per page
            sort_by: Column to sort by
            sort_dir: Sort direction ('asc' or 'desc')
            filters: Dict mapping column keys to filter strings
            fiscal_year: Fiscal year filter (currently not used in Project model)

        Returns:
            Dict with 'total', 'filtered', and 'rows' keys
        """
        if filters is None:
            filters = {}

        # Base project query (restricted to agency codes starting with '521')
        base_q = db.session.query(Project).filter(
            Project.agency_code.isnot(None),
            Project.agency_code.like('521%')
        )

        total = base_q.count()

        # Build subquery to get the most recent matched survey per project using window function
        sr_sub = (
            db.session.query(
                SurveyResponse.id.label('sr_id'),
                SurveyResponse.project_id.label('sr_project_id'),
                SurveyResponse.health_care_service.label('health_care_service'),
                SurveyResponse.intermediate_outcome.label('intermediate_outcome'),
                SurveyResponse.category.label('category'),
                SurveyResponse.primary_health_care.label('primary'),
                SurveyResponse.secondary_health_care.label('secondary'),
                SurveyResponse.tertiary_health_care.label('tertiary'),
                func.row_number().over(
                    partition_by=SurveyResponse.project_id,
                    order_by=SurveyResponse.import_date.desc()
                ).label('rn')
            )
            .filter(SurveyResponse.is_matched == True)
            .subquery()
        )

        latest = db.session.query(sr_sub).filter(sr_sub.c.rn == 1).subquery()

        # Join projects to latest survey (left join so projects without surveys still appear)
        q = db.session.query(
            Project,
            latest.c.health_care_service,
            latest.c.intermediate_outcome,
            latest.c.category,
            latest.c.primary,
            latest.c.secondary,
            latest.c.tertiary,
        ).outerjoin(
            latest, Project.id == latest.c.sr_project_id
        ).filter(
            Project.agency_code.isnot(None),
            Project.agency_code.like('521%')
        )

        # Apply filters
        # Apply filters - now can do exact enum matching
        if filters:
            filter_clauses = []
            for key, val in filters.items():
                if not val:
                    continue
                
                if key == 'intermediate_outcome':
                    # Try to match against enum values
                    enum_val = IntermediateOutcome(val)
                    if enum_val:
                        filter_clauses.append(latest.c.intermediate_outcome == enum_val)
                    else:
                        # Fallback to text search
                        filter_clauses.append(latest.c.intermediate_outcome.ilike(f"%{val}%"))
                
                elif key == 'category':
                    enum_val = BudgetCategory(val)
                    if enum_val:
                        filter_clauses.append(latest.c.category == enum_val)
                    else:
                        filter_clauses.append(latest.c.category.ilike(f"%{val}%"))
                
                elif key == 'health_care_service':
                    enum_val = HealthCareService(val)
                    if enum_val:
                        filter_clauses.append(latest.c.health_care_service == enum_val)
                    else:
                        filter_clauses.append(latest.c.health_care_service.ilike(f"%{val}%"))
                
                elif key == 'service_detail':
                    # For service detail, we need to check the appropriate enum based on health_care_service
                    # This is more complex - you might want to handle this at the application level
                    filter_clauses.append(
                        or_(
                            latest.c.primary == val,
                            latest.c.secondary == val,
                            latest.c.tertiary == val
                        )
                    )

            if filter_clauses:
                q = q.filter(and_(*filter_clauses))

        # Get filtered count
        filtered_count_q = q.with_entities(func.count(func.distinct(Project.id)))
        filtered = filtered_count_q.scalar() or 0

        # Sorting
        sort_map = {
            'code': Project.code,
            'project_name': Project.project_name,
            'agency': Project.agency_name,
            'health_care_service': latest.c.health_care_service,
            'intermediate_outcome': latest.c.intermediate_outcome,
            'category': latest.c.category,
            'service_detail': latest.c.primary,  # Sort by primary by default
            'appropriation': Project.appropriation,
        }

        if sort_by in sort_map:
            col = sort_map[sort_by]
            if sort_dir == 'desc':
                q = q.order_by(desc(col).nullslast())
            else:
                q = q.order_by(col.nullslast())
        else:
            # Default sort by project name
            q = q.order_by(Project.project_name)

        # Pagination
        q = q.offset(start).limit(length)

        results = q.all()

        rows = []
        for row in results:
            proj = row[0]
            # Format enum values for frontend display
            health_service = format_enum_for_display(row[1])
            intermediate = format_enum_for_display(row[2])
            category = format_enum_for_display(row[3])
            primary = format_enum_for_display(row[4])
            secondary = format_enum_for_display(row[5])
            tertiary = format_enum_for_display(row[6])

            # Intelligently choose service_detail based on health_care_service level
            service_detail = None
            if health_service:
                health_service_lower = health_service.lower()
                if 'tertiary' in health_service_lower:
                    service_detail = tertiary
                elif 'secondary' in health_service_lower:
                    service_detail = secondary
                elif 'primary' in health_service_lower:
                    service_detail = primary
                else:
                    # Fallback if health_care_service doesn't match expected pattern
                    service_detail = primary or secondary or tertiary
            else:
                # No health_care_service, use priority order
                service_detail = primary or secondary or tertiary

            rows.append({
                'code': proj.code,
                'project_name': proj.project_name,
                'agency': proj.agency_name or proj.agency_code,
                'health_care_service': health_service,
                'intermediate_outcome': intermediate,
                'category': category,
                'service_detail': service_detail,
                'appropriation': float(proj.appropriation) if proj.appropriation is not None else None,
                'id': proj.id,
            })

        return {
            'total': total,
            'filtered': filtered,
            'rows': rows,
        }


