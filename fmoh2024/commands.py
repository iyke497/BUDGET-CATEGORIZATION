# fmoh2024/commands.py
import click
import pandas as pd
from flask.cli import with_appcontext
from datetime import datetime
from fmoh2024.extensions import db
from fmoh2024.models import MinistryAgency, Project


def normalize_name(name):
    """Normalize ministry/agency names for consistent matching"""
    if pd.isna(name) or not isinstance(name, str):
        return ""
    return MinistryAgency.normalize_name(name)


@click.command('import-excel')
@click.argument('filename')
@click.option('--sheet', default=0, help='Sheet name or index to import')
@click.option('--fiscal-year', default='2024', help='Fiscal year for the data')
@with_appcontext
def import_excel_command(filename, sheet, fiscal_year):
    """Import budget data from Excel file into the database."""
    click.echo(f"📂 Importing data from {filename}...")
    
    try:
        # Read Excel file
        df = pd.read_excel(filename, sheet_name=sheet)
        click.echo(f"✅ Found {len(df)} rows in Excel file")
        
        # Standardize column names (remove spaces, uppercase)
        df.columns = [col.strip().upper().replace(' ', '_') for col in df.columns]
        click.echo(f"📋 Columns found: {', '.join(df.columns)}")
        
        # Track statistics
        stats = {
            'agencies_created': 0,
            'agencies_updated': 0,
            'projects_created': 0,
            'projects_skipped': 0,
            'errors': 0
        }
        
        # First pass: Process all unique ministry-agency combinations
        click.echo("\n🏢 Processing ministries and agencies...")
        
        # Create a unique key for each ministry-agency combination
        agency_records = {}
        
        for idx, row in df.iterrows():
            try:
                # Skip if no agency code
                if pd.isna(row.get('AGENCY_CODE')):
                    continue
                
                agency_code = str(row['AGENCY_CODE']).strip()
                ministry_code = str(row.get('MINISTRY_CODE', '')).strip() if not pd.isna(row.get('MINISTRY_CODE')) else None
                
                # Create a unique key
                key = f"{ministry_code}|{agency_code}"
                
                if key not in agency_records:
                    agency_records[key] = {
                        'ministry_code': ministry_code,
                        'agency_code': agency_code,
                        'ministry_name': row.get('MINISTRY', ''),
                        'agency_name': row.get('AGENCY', ''),
                        'fiscal_year': fiscal_year
                    }
                    
            except Exception as e:
                click.echo(f"⚠️  Error processing row {idx + 2}: {e}", err=True)
                stats['errors'] += 1
        
        click.echo(f"✅ Found {len(agency_records)} unique ministry-agency combinations")
        
        # Insert/update ministry agencies
        for key, agency_data in agency_records.items():
            try:
                # Check if agency already exists
                agency = MinistryAgency.query.filter_by(
                    agency_code=agency_data['agency_code'],
                    fiscal_year=fiscal_year
                ).first()
                
                if agency:
                    # Update existing agency
                    agency.ministry_code = agency_data['ministry_code']
                    agency.ministry_name = agency_data['ministry_name']
                    agency.agency_name = agency_data['agency_name']
                    agency.agency_name_normalized = normalize_name(agency_data['agency_name'])
                    agency.ministry_name_normalized = normalize_name(agency_data['ministry_name'])
                    agency.updated_at = datetime.utcnow()
                    stats['agencies_updated'] += 1
                else:
                    # Create new agency
                    agency = MinistryAgency(
                        ministry_code=agency_data['ministry_code'],
                        agency_code=agency_data['agency_code'],
                        ministry_name=agency_data['ministry_name'],
                        agency_name=agency_data['agency_name'],
                        fiscal_year=fiscal_year,
                        is_active=True
                    )
                    db.session.add(agency)
                    stats['agencies_created'] += 1
                
                # Commit every 100 agencies to avoid memory issues
                if (stats['agencies_created'] + stats['agencies_updated']) % 100 == 0:
                    db.session.commit()
                    click.echo(f"  ⏳ Processed {stats['agencies_created'] + stats['agencies_updated']} agencies...")
                    
            except Exception as e:
                click.echo(f"⚠️  Error saving agency {agency_data['agency_code']}: {e}", err=True)
                stats['errors'] += 1
                db.session.rollback()
        
        # Final commit for agencies
        db.session.commit()
        click.echo(f"✅ Agencies: {stats['agencies_created']} created, {stats['agencies_updated']} updated")
        
        # Second pass: Import projects
        click.echo("\n📊 Importing projects...")
        
        for idx, row in df.iterrows():
            try:
                # Skip rows without ERGP code
                if pd.isna(row.get('ERGP_CODE')):
                    stats['projects_skipped'] += 1
                    continue
                
                # Find the agency
                agency = None
                if not pd.isna(row.get('AGENCY_CODE')):
                    agency = MinistryAgency.query.filter_by(
                        agency_code=str(row['AGENCY_CODE']).strip(),
                        fiscal_year=fiscal_year,
                        is_active=True
                    ).first()
                
                # Prepare project data
                project_data = {
                    'code': str(row['ERGP_CODE']).strip(),
                    'project_name': row.get('PROJECT_NAME', ''),
                    'project_status': row.get('STATUS', ''),
                    'appropriation': row.get('APPROPRIATION', 0) if not pd.isna(row.get('APPROPRIATION')) else 0,
                    'ministry_code': str(row.get('MINISTRY_CODE', '')).strip() if not pd.isna(row.get('MINISTRY_CODE')) else None,
                    'ministry_name': row.get('MINISTRY', ''),
                    'agency_code': str(row.get('AGENCY_CODE', '')).strip() if not pd.isna(row.get('AGENCY_CODE')) else None,
                    'agency_name': row.get('AGENCY', ''),
                    'agency_normalized': normalize_name(row.get('AGENCY', ''))
                }
                
                # Check if project already exists (by code + agency)
                existing_project = None
                if agency:
                    existing_project = Project.query.filter_by(
                        code=project_data['code'],
                        agency_id=agency.id
                    ).first()
                else:
                    # If no agency, try to find by code and null agency
                    existing_project = Project.query.filter(
                        Project.code == project_data['code'],
                        Project.agency_id.is_(None)
                    ).first()
                
                if existing_project:
                    # Update existing project
                    for key, value in project_data.items():
                        if hasattr(existing_project, key):
                            setattr(existing_project, key, value)
                    if agency:
                        existing_project.agency_id = agency.id
                    stats['projects_skipped'] += 1  # Counting as skipped since we're not creating new
                else:
                    # Create new project
                    project = Project(**project_data)
                    if agency:
                        project.agency_id = agency.id
                    db.session.add(project)
                    stats['projects_created'] += 1
                
                # Commit every 100 projects
                if stats['projects_created'] % 100 == 0 and stats['projects_created'] > 0:
                    db.session.commit()
                    click.echo(f"  ⏳ Imported {stats['projects_created']} projects...")
                    
            except Exception as e:
                click.echo(f"⚠️  Error importing project at row {idx + 2}: {e}", err=True)
                stats['errors'] += 1
                db.session.rollback()
        
        # Final commit for projects
        db.session.commit()
        
        # Print summary
        click.echo("\n" + "="*50)
        click.echo("📊 IMPORT SUMMARY")
        click.echo("="*50)
        click.echo(f"🏢 Agencies: {stats['agencies_created']} created, {stats['agencies_updated']} updated")
        click.echo(f"📊 Projects: {stats['projects_created']} created, {stats['projects_skipped']} skipped")
        click.echo(f"⚠️  Errors: {stats['errors']}")
        click.echo("="*50)
        
    except Exception as e:
        click.echo(f"❌ Error reading Excel file: {e}", err=True)
        db.session.rollback()
        return


@click.command('clear-data')
@click.option('--fiscal-year', default='2024', help='Fiscal year to clear')
@click.confirmation_option(prompt='Are you sure you want to delete all data?')
@with_appcontext
def clear_data_command(fiscal_year):
    """Clear all imported data for a specific fiscal year."""
    click.echo(f"🧹 Clearing data for fiscal year {fiscal_year}...")
    
    try:
        # Delete projects first (due to foreign key constraints)
        Project.query.filter(
            Project.created_at.isnot(None)  # Simple filter, adjust as needed
        ).delete(synchronize_session=False)
        
        # Delete ministry agencies
        MinistryAgency.query.filter_by(fiscal_year=fiscal_year).delete(synchronize_session=False)
        
        db.session.commit()
        click.echo("✅ Data cleared successfully!")
        
    except Exception as e:
        click.echo(f"❌ Error clearing data: {e}", err=True)
        db.session.rollback()


@click.command('list-agencies')
@click.option('--fiscal-year', default='2024', help='Fiscal year to list')
@with_appcontext
def list_agencies_command(fiscal_year):
    """List all agencies in the database."""
    agencies = MinistryAgency.query.filter_by(
        fiscal_year=fiscal_year,
        is_active=True
    ).order_by(MinistryAgency.ministry_name, MinistryAgency.agency_name).all()
    
    click.echo(f"\n📋 Agencies for fiscal year {fiscal_year}:")
    click.echo("="*80)
    
    for agency in agencies:
        project_count = agency.projects.count()
        click.echo(f"{agency.agency_code}: {agency.agency_name}")
        click.echo(f"  ├─ Ministry: {agency.ministry_name} ({agency.ministry_code})")
        click.echo(f"  ├─ Self-accounting: {agency.is_self_accounting}")
        click.echo(f"  └─ Projects: {project_count}")
        click.echo()
    
    click.echo(f"Total: {len(agencies)} agencies")

@click.command('clean-agency-codes')
@click.option('--fiscal-year', default='2024', help='Fiscal year to clean')
@with_appcontext
def clean_agency_codes_command(fiscal_year):
    """Clean agency codes by removing .0 suffix."""
    click.echo(f"🧹 Cleaning agency codes for fiscal year {fiscal_year}...")
    
    # Fix MinistryAgency codes
    agencies = MinistryAgency.query.filter_by(fiscal_year=fiscal_year).all()
    fixed_count = 0
    
    for agency in agencies:
        if agency.agency_code and agency.agency_code.endswith('.0'):
            old_code = agency.agency_code
            agency.agency_code = agency.agency_code[:-2]
            click.echo(f"  Fixed: {old_code} -> {agency.agency_code}")
            fixed_count += 1
    
    db.session.commit()
    click.echo(f"✅ Fixed {fixed_count} agency codes")
    
    # Also fix project agency codes
    projects = Project.query.filter(
        Project.agency_code.isnot(None),
        Project.agency_code.endswith('.0')
    ).all()
    
    fixed_projects = 0
    for project in projects:
        old_code = project.agency_code
        project.agency_code = project.agency_code[:-2]
        fixed_projects += 1
    
    db.session.commit()
    click.echo(f"✅ Fixed {fixed_projects} project agency codes")

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Create database tables."""
    click.echo("🗄️  Creating database tables...")
    db.create_all()
    click.echo("✅ Database tables created successfully!")

def register_commands(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(import_excel_command)
    app.cli.add_command(clear_data_command)
    app.cli.add_command(list_agencies_command)
    app.cli.add_command(clean_agency_codes_command)
    app.cli.add_command(init_db_command)