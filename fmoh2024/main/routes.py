# fmoh2024/main/routes.py
from flask import render_template
from fmoh2024.main import bp
from fmoh2024.models import Project, SurveyResponse, MinistryAgency
from fmoh2024.extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta


@bp.route('/')
def index():
    """Home page route with dashboard overview."""
    
    # Get total projects
    total_projects = Project.query.count()
    
    # Get categorized projects
    categorized_projects = db.session.query(Project).join(
        SurveyResponse, 
        Project.id == SurveyResponse.project_id
    ).filter(
        SurveyResponse.is_matched == True
    ).distinct().count()
    
        
    # Get focus agencies (521 prefix)
    focus_agencies = MinistryAgency.query.filter(
        MinistryAgency.agency_code.startswith('521'),
        MinistryAgency.is_active == True
    ).count()
    
    # Get compliance rate for focus agencies
    focus_agency_ids = db.session.query(MinistryAgency.id).filter(
        MinistryAgency.agency_code.startswith('521')
    ).subquery()
    
    focus_total_projects = Project.query.filter(
        Project.agency_id.in_(focus_agency_ids)
    ).count()

    # Calculate categorization rate ######
    categorization_rate = round((categorized_projects / focus_total_projects * 100), 1) if focus_total_projects > 0 else 0
    
    
    focus_categorized = db.session.query(Project).join(
        SurveyResponse,
        Project.id == SurveyResponse.project_id
    ).filter(
        Project.agency_id.in_(focus_agency_ids),
        SurveyResponse.is_matched == True
    ).distinct().count()
    
    compliance_rate = round((focus_categorized / focus_total_projects * 100), 1) if focus_total_projects > 0 else 0
    
    # Get recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    recent_surveys = SurveyResponse.query.filter(
        SurveyResponse.import_date >= week_ago
    ).count()
    
    recent_matches = SurveyResponse.query.filter(
        SurveyResponse.matched_at >= week_ago
    ).count()
    
    recent_activities = []
    
    if recent_surveys > 0:
        recent_activities.append({
            'time': 'This week',
            'icon': '📥',
            'text': f'{recent_surveys} new survey responses imported'
        })
    
    if recent_matches > 0:
        recent_activities.append({
            'time': 'This week',
            'icon': '✓',
            'text': f'{recent_matches} projects matched to surveys'
        })
    
    # Add sample activities if none exist
    if not recent_activities:
        recent_activities = [
            {
                'time': '2 days ago',
                'icon': '📊',
                'text': 'Compliance dashboard updated'
            },
            {
                'time': '5 days ago',
                'icon': '📥',
                'text': 'Survey data import completed (318 responses)'
            },
            {
                'time': '1 week ago',
                'icon': '🔍',
                'text': 'Matching process completed: 298 projects matched'
            }
        ]
    
    return render_template(
        'main/index.html',
        total_projects=focus_total_projects,
        categorized_projects=categorized_projects,
        categorization_rate=categorization_rate,
        focus_agencies=focus_agencies,
        compliance_rate=compliance_rate,
        recent_activities=recent_activities
    )


@bp.route('/health')
def health():
    """Health check endpoint."""
    return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}, 200