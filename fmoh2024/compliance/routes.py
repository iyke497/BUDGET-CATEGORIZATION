# fmoh2024/compliance/routes.py
from flask import render_template, jsonify, request
from fmoh2024.compliance import bp
from fmoh2024.compliance.services import ComplianceService


@bp.route('/')
def dashboard():
    """Main compliance dashboard showing all agencies."""
    fiscal_year = request.args.get('fiscal_year', '2024')
    
    # Get compliance data
    compliance_data = ComplianceService.get_all_compliance_stats(fiscal_year)
    summary = ComplianceService.get_summary_stats(fiscal_year)
    
    return render_template(
        'compliance/dashboard.html',
        compliance_data=compliance_data,
        summary=summary,
        fiscal_year=fiscal_year
    )


@bp.route('/agency/<int:agency_id>')
def agency_detail(agency_id):
    """Detailed view for a specific agency."""
    fiscal_year = request.args.get('fiscal_year', '2024')
    
    details = ComplianceService.get_agency_project_details(agency_id, fiscal_year)
    
    if not details:
        return "Agency not found", 404
    
    return render_template(
        'compliance/agency_detail.html',
        details=details,
        fiscal_year=fiscal_year
    )


@bp.route('/api/compliance')
def api_compliance():
    """API endpoint for compliance data (for charts/JS)."""
    fiscal_year = request.args.get('fiscal_year', '2024')
    compliance_data = ComplianceService.get_all_compliance_stats(fiscal_year)
    summary = ComplianceService.get_summary_stats(fiscal_year)
    
    return jsonify({
        'summary': summary,
        'agencies': [
            {
                'id': item['agency'].id,
                'name': item['agency'].agency_name,
                'ministry': item['agency'].ministry_name,
                'code': item['agency'].agency_code,
                'total_projects': item['total_projects'],
                'categorized': item['categorized_projects'],
                'compliance': item['compliance_percentage'],
                'status': item['status']
            }
            for item in compliance_data
        ]
    })
