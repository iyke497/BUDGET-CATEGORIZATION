# fmoh2024/projects/routes.py
from flask import render_template, jsonify, request
from fmoh2024.projects import bp
from fmoh2024.projects.services import ProjectsService


@bp.route('/')
def index():
    """Projects landing page."""
    fiscal_year = request.args.get('fiscal_year', '2024')
    return render_template('projects/index.html', fiscal_year=fiscal_year)


@bp.route('/api')
def api_projects():
    """API endpoint returning projects list as JSON for DataTables."""
    fiscal_year = request.args.get('fiscal_year', '2024')
    
    # Server-side DataTables parameters
    try:
        draw = int(request.args.get('draw', 1))
        start = int(request.args.get('start', 0))
        length = int(request.args.get('length', 10))
    except (ValueError, TypeError):
        draw = 1
        start = 0
        length = 10

    # Get sorting parameters
    order_col = request.args.get('order[0][column]')
    order_dir = request.args.get('order[0][dir]', 'asc')

    # Column mapping consistent with template
    columns = [
        'code',
        'project_name',
        'agency',
        'health_care_service',
        'intermediate_outcome',
        'category',
        'service_detail'
    ]

    sort_by = None
    if order_col is not None and order_col.isdigit():
        idx = int(order_col)
        if 0 <= idx < len(columns):
            sort_by = columns[idx]

    # Collect column searches
    filters = {}
    for i, col in enumerate(columns):
        val = request.args.get(f'columns[{i}][search][value]')
        if val and val.strip():
            filters[col] = val.strip()

    try:
        # Get paginated data from service
        page = ProjectsService.get_projects_page(
            start=start,
            length=length,
            sort_by=sort_by,
            sort_dir=order_dir,
            filters=filters,
            fiscal_year=fiscal_year
        )

        return jsonify({
            'draw': draw,
            'recordsTotal': page['total'],
            'recordsFiltered': page['filtered'],
            'data': page['rows']
        })
    
    except Exception as e:
        # Log the error and return empty result
        import traceback
        print(f"Error in api_projects: {str(e)}")
        print(traceback.format_exc())
        
        return jsonify({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': str(e)
        }), 500


@bp.route('/api/<int:project_id>')
def api_project_detail(project_id):
    """API endpoint for single project detail."""
    fiscal_year = request.args.get('fiscal_year', '2024')
    
    try:
        project = ProjectsService.get_project_by_id(project_id, fiscal_year)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        return jsonify(project.to_dict())
    
    except Exception as e:
        import traceback
        print(f"Error in api_project_detail: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500