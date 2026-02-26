# fmoh2024/commands.py
import logging
import os
import tempfile
import time
from datetime import datetime

import click
import pandas as pd
import requests
from flask.cli import with_appcontext

from fmoh2024.extensions import db
from fmoh2024.models import MinistryAgency, Project, SurveyResponse, IntermediateOutcome, BudgetCategory, HealthCareService, PrimaryHealthService, SecondaryHealthService, TertiaryHealthService

logger = logging.getLogger(__name__)


def normalize_name(name):
    """Normalize ministry/agency names for consistent matching"""
    if pd.isna(name) or not isinstance(name, str):
        return ""
    return MinistryAgency.normalize_name(name)


@click.command("import-excel")
@click.argument("filename")
@click.option("--sheet", default=0, help="Sheet name or index to import")
@click.option("--fiscal-year", default="2024", help="Fiscal year for the data")
@with_appcontext
def import_excel_command(filename, sheet, fiscal_year):
    """Import budget data from Excel file into the database."""
    click.echo(f"📂 Importing data from {filename}...")

    try:
        # Read Excel file
        df = pd.read_excel(filename, sheet_name=sheet)
        click.echo(f"✅ Found {len(df)} rows in Excel file")

        # Standardize column names (remove spaces, uppercase)
        df.columns = [col.strip().upper().replace(" ", "_") for col in df.columns]
        click.echo(f"📋 Columns found: {', '.join(df.columns)}")

        # Track statistics
        stats = {
            "agencies_created": 0,
            "agencies_updated": 0,
            "projects_created": 0,
            "projects_skipped": 0,
            "errors": 0,
        }

        # First pass: Process all unique ministry-agency combinations
        click.echo("\n🏢 Processing ministries and agencies...")

        # Create a unique key for each ministry-agency combination
        agency_records = {}

        for idx, row in df.iterrows():
            try:
                # Skip if no agency code
                if pd.isna(row.get("AGENCY_CODE")):
                    continue

                agency_code = str(row["AGENCY_CODE"]).strip()
                ministry_code = (
                    str(row.get("MINISTRY_CODE", "")).strip()
                    if not pd.isna(row.get("MINISTRY_CODE"))
                    else None
                )

                # Create a unique key
                key = f"{ministry_code}|{agency_code}"

                if key not in agency_records:
                    agency_records[key] = {
                        "ministry_code": ministry_code,
                        "agency_code": agency_code,
                        "ministry_name": row.get("MINISTRY", ""),
                        "agency_name": row.get("AGENCY", ""),
                        "fiscal_year": fiscal_year,
                    }

            except Exception as e:
                click.echo(f"⚠️  Error processing row {idx + 2}: {e}", err=True)
                stats["errors"] += 1

        click.echo(
            f"✅ Found {len(agency_records)} unique ministry-agency combinations"
        )

        # Insert/update ministry agencies
        for key, agency_data in agency_records.items():
            try:
                # Check if agency already exists
                agency = MinistryAgency.query.filter_by(
                    agency_code=agency_data["agency_code"], fiscal_year=fiscal_year
                ).first()

                if agency:
                    # Update existing agency
                    agency.ministry_code = agency_data["ministry_code"]
                    agency.ministry_name = agency_data["ministry_name"]
                    agency.agency_name = agency_data["agency_name"]
                    agency.agency_name_normalized = normalize_name(
                        agency_data["agency_name"]
                    )
                    agency.ministry_name_normalized = normalize_name(
                        agency_data["ministry_name"]
                    )
                    agency.updated_at = datetime.utcnow()
                    stats["agencies_updated"] += 1
                else:
                    # Create new agency
                    agency = MinistryAgency(
                        ministry_code=agency_data["ministry_code"],
                        agency_code=agency_data["agency_code"],
                        ministry_name=agency_data["ministry_name"],
                        agency_name=agency_data["agency_name"],
                        fiscal_year=fiscal_year,
                        is_active=True,
                    )
                    db.session.add(agency)
                    stats["agencies_created"] += 1

                # Commit every 100 agencies to avoid memory issues
                if (stats["agencies_created"] + stats["agencies_updated"]) % 100 == 0:
                    db.session.commit()
                    click.echo(
                        f"  ⏳ Processed {stats['agencies_created'] + stats['agencies_updated']} agencies..."
                    )

            except Exception as e:
                click.echo(
                    f"⚠️  Error saving agency {agency_data['agency_code']}: {e}",
                    err=True,
                )
                stats["errors"] += 1
                db.session.rollback()

        # Final commit for agencies
        db.session.commit()
        click.echo(
            f"✅ Agencies: {stats['agencies_created']} created, {stats['agencies_updated']} updated"
        )

        # Second pass: Import projects
        click.echo("\n📊 Importing projects...")

        for idx, row in df.iterrows():
            try:
                # Skip rows without ERGP code
                if pd.isna(row.get("ERGP_CODE")):
                    stats["projects_skipped"] += 1
                    continue

                # Find the agency
                agency = None
                if not pd.isna(row.get("AGENCY_CODE")):
                    agency = MinistryAgency.query.filter_by(
                        agency_code=str(row["AGENCY_CODE"]).strip(),
                        fiscal_year=fiscal_year,
                        is_active=True,
                    ).first()

                # Prepare project data
                project_data = {
                    "code": str(row["ERGP_CODE"]).strip(),
                    "project_name": row.get("PROJECT_NAME", ""),
                    "project_status": row.get("STATUS", ""),
                    "appropriation": (
                        row.get("APPROPRIATION", 0)
                        if not pd.isna(row.get("APPROPRIATION"))
                        else 0
                    ),
                    "ministry_code": (
                        str(row.get("MINISTRY_CODE", "")).strip()
                        if not pd.isna(row.get("MINISTRY_CODE"))
                        else None
                    ),
                    "ministry_name": row.get("MINISTRY", ""),
                    "agency_code": (
                        str(row.get("AGENCY_CODE", "")).strip()
                        if not pd.isna(row.get("AGENCY_CODE"))
                        else None
                    ),
                    "agency_name": row.get("AGENCY", ""),
                    "agency_normalized": normalize_name(row.get("AGENCY", "")),
                }

                # Check if project already exists (by code + agency)
                existing_project = None
                if agency:
                    existing_project = Project.query.filter_by(
                        code=project_data["code"], agency_id=agency.id
                    ).first()
                else:
                    # If no agency, try to find by code and null agency
                    existing_project = Project.query.filter(
                        Project.code == project_data["code"],
                        Project.agency_id.is_(None),
                    ).first()

                if existing_project:
                    # Update existing project
                    for key, value in project_data.items():
                        if hasattr(existing_project, key):
                            setattr(existing_project, key, value)
                    if agency:
                        existing_project.agency_id = agency.id
                    stats[
                        "projects_skipped"
                    ] += 1  # Counting as skipped since we're not creating new
                else:
                    # Create new project
                    project = Project(**project_data)
                    if agency:
                        project.agency_id = agency.id
                    db.session.add(project)
                    stats["projects_created"] += 1

                # Commit every 100 projects
                if (
                    stats["projects_created"] % 100 == 0
                    and stats["projects_created"] > 0
                ):
                    db.session.commit()
                    click.echo(f"  ⏳ Imported {stats['projects_created']} projects...")

            except Exception as e:
                click.echo(
                    f"⚠️  Error importing project at row {idx + 2}: {e}", err=True
                )
                stats["errors"] += 1
                db.session.rollback()

        # Final commit for projects
        db.session.commit()

        # Print summary
        click.echo("\n" + "=" * 50)
        click.echo("📊 IMPORT SUMMARY")
        click.echo("=" * 50)
        click.echo(
            f"🏢 Agencies: {stats['agencies_created']} created, {stats['agencies_updated']} updated"
        )
        click.echo(
            f"📊 Projects: {stats['projects_created']} created, {stats['projects_skipped']} skipped"
        )
        click.echo(f"⚠️  Errors: {stats['errors']}")
        click.echo("=" * 50)

    except Exception as e:
        click.echo(f"❌ Error reading Excel file: {e}", err=True)
        db.session.rollback()
        return


@click.command("clear-data")
@click.option("--fiscal-year", default="2024", help="Fiscal year to clear")
@click.confirmation_option(prompt="Are you sure you want to delete all data?")
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
        MinistryAgency.query.filter_by(fiscal_year=fiscal_year).delete(
            synchronize_session=False
        )

        db.session.commit()
        click.echo("✅ Data cleared successfully!")

    except Exception as e:
        click.echo(f"❌ Error clearing data: {e}", err=True)
        db.session.rollback()


@click.command("list-agencies")
@click.option("--fiscal-year", default="2024", help="Fiscal year to list")
@with_appcontext
def list_agencies_command(fiscal_year):
    """List all agencies in the database."""
    agencies = (
        MinistryAgency.query.filter_by(fiscal_year=fiscal_year, is_active=True)
        .order_by(MinistryAgency.ministry_name, MinistryAgency.agency_name)
        .all()
    )

    click.echo(f"\n📋 Agencies for fiscal year {fiscal_year}:")
    click.echo("=" * 80)

    for agency in agencies:
        project_count = agency.projects.count()
        click.echo(f"{agency.agency_code}: {agency.agency_name}")
        click.echo(f"  ├─ Ministry: {agency.ministry_name} ({agency.ministry_code})")
        click.echo(f"  ├─ Self-accounting: {agency.is_self_accounting}")
        click.echo(f"  └─ Projects: {project_count}")
        click.echo()

    click.echo(f"Total: {len(agencies)} agencies")


@click.command("clean-agency-codes")
@click.option("--fiscal-year", default="2024", help="Fiscal year to clean")
@with_appcontext
def clean_agency_codes_command(fiscal_year):
    """Clean agency codes by removing .0 suffix."""
    click.echo(f"🧹 Cleaning agency codes for fiscal year {fiscal_year}...")

    # Fix MinistryAgency codes
    agencies = MinistryAgency.query.filter_by(fiscal_year=fiscal_year).all()
    fixed_count = 0

    for agency in agencies:
        if agency.agency_code and agency.agency_code.endswith(".0"):
            old_code = agency.agency_code
            agency.agency_code = agency.agency_code[:-2]
            click.echo(f"  Fixed: {old_code} -> {agency.agency_code}")
            fixed_count += 1

    db.session.commit()
    click.echo(f"✅ Fixed {fixed_count} agency codes")

    # Also fix project agency codes
    projects = Project.query.filter(
        Project.agency_code.isnot(None), Project.agency_code.endswith(".0")
    ).all()

    fixed_projects = 0
    for project in projects:
        old_code = project.agency_code
        project.agency_code = project.agency_code[:-2]
        fixed_projects += 1

    db.session.commit()
    click.echo(f"✅ Fixed {fixed_projects} project agency codes")


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create database tables."""
    click.echo("🗄️  Creating database tables...")
    db.create_all()
    click.echo("✅ Database tables created successfully!")


@click.command("fetch-survey-data")
@click.option(
    "--bearer-token",
    envvar="SURVEY_BEARER_TOKEN",
    help="Bearer token for API authentication (or set SURVEY_BEARER_TOKEN env var)",
)
@click.option(
    "--org-id",
    envvar="ORGANIZATION_ID",
    help="Organization ID for API authentication (or set ORGANIZATION_ID env var)",
)
@click.option(
    "--base-url", default="https://api.eyemark.ng", help="Base URL for the API"
)
@click.option(
    "--survey-id",
    default="35e0adf5-11b2-456b-8f84-071a3129f20b",
    help="Survey ID to fetch",
)
@click.option(
    "--poll-interval", default=5, help="Seconds between status polling attempts"
)
@click.option("--max-attempts", default=60, help="Maximum number of polling attempts")
@click.option("--fiscal-year", default="2024", help="Fiscal year for this data")
@with_appcontext
def fetch_survey_data_command(
    bearer_token, org_id, base_url, survey_id, poll_interval, max_attempts, fiscal_year
):
    """
    Fetch survey data from Eyemark API:
    1. Triggers report generation
    2. Polls for status until ready
    3. Downloads the Excel file
    4. Imports data into SurveyResponse table
    """

    if not bearer_token or not org_id:
        click.echo(
            "❌ Error: Both bearer token and organization ID are required", err=True
        )
        click.echo("   Set them via --bearer-token/--org-id or environment variables")
        return

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "X-Organization-ID": org_id,
        "Content-Type": "application/json",
    }

    # Step 1: Trigger report generation
    trigger_url = f"{base_url}/api/surveys/{survey_id}/report/"
    click.echo(f"🔄 Triggering report generation for survey {survey_id}...")

    try:
        trigger_response = requests.get(trigger_url, headers=headers)
        trigger_response.raise_for_status()
        trigger_data = trigger_response.json()
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Failed to trigger report: {e}", err=True)
        return
    except ValueError as e:
        click.echo(f"❌ Invalid JSON response: {e}", err=True)
        return

    if not trigger_data.get("status"):
        click.echo(
            f"❌ API error: {trigger_data.get('message', 'Unknown error')}", err=True
        )
        return

    task_id = trigger_data["data"]["task_id"]
    click.echo(f"✅ Report generation triggered! Task ID: {task_id}")

    # Step 2: Poll for status
    status_url = f"{base_url}/api/surveys/report-status/"
    click.echo(f"⏳ Polling for status (will check every {poll_interval} seconds)...")

    for attempt in range(max_attempts):
        time.sleep(poll_interval)

        try:
            status_response = requests.get(
                status_url, headers=headers, params={"task_id": task_id}
            )
            status_response.raise_for_status()
            status_data = status_response.json()
        except requests.exceptions.RequestException as e:
            click.echo(f"⚠️  Polling error (attempt {attempt + 1}): {e}", err=True)
            continue

        if not status_data.get("status"):
            click.echo(f"⚠️  API error: {status_data.get('message', 'Unknown error')}")
            continue

        current_status = status_data["data"]["status"]
        click.echo(f"   Status: {current_status}")

        if current_status == "SUCCESS":
            file_url = status_data["data"]["result"]["file_url"]
            filename = status_data["data"]["result"]["filename"]
            total_responses = status_data["data"]["result"].get(
                "total_responses", "unknown"
            )
            click.echo(f"✅ Report ready! {total_responses} responses available")
            click.echo(f"   Filename: {filename}")
            break
        elif current_status == "FAILURE":
            click.echo("❌ Report generation failed", err=True)
            return
        elif current_status in ["PENDING", "PROCESSING", "STARTED"]:
            continue
        else:
            click.echo(f"⚠️  Unknown status: {current_status}")
            continue
    else:
        click.echo(f"❌ Timed out after {max_attempts} polling attempts", err=True)
        return

    # Step 3: Download the Excel file
    click.echo("📥 Downloading Excel file...")

    try:
        # Download with streaming to handle large files
        file_response = requests.get(file_url, stream=True)
        file_response.raise_for_status()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            for chunk in file_response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            temp_path = tmp_file.name

        click.echo(f"✅ Downloaded to temporary file: {temp_path}")

        # Step 4: Import the Excel data
        import_survey_excel(temp_path, fiscal_year, task_id)

        # Clean up temp file
        os.unlink(temp_path)
        click.echo(f"🧹 Cleaned up temporary file: {temp_path}")

    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Failed to download file: {e}", err=True)
        return
    except Exception as e:
        click.echo(f"❌ Error processing file: {e}", err=True)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return


def parse_enum_field(value, enum_class):
    """
    Parse a value into an enum using the enum's _missing_ method.
    Returns None if value is invalid or empty.
    """
    if pd.isna(value) or value is None:
        return None
    
    # Convert to string and clean
    str_value = str(value).strip()
    
    # Handle 'nan' strings from pandas
    if str_value.lower() == 'nan' or str_value == '':
        return None
    
    try:
        # Use the enum's _missing_ method which handles partial matches
        result = enum_class(str_value)
        
        # If result is None but we have a value, try to map to OTHER
        if result is None and hasattr(enum_class, 'OTHER'):
            return enum_class.OTHER
        elif result is None and hasattr(enum_class, 'OTHERS'):
            return enum_class.OTHERS
            
        return result
    except (ValueError, KeyError):
        # If enum doesn't have _missing_ or it fails, try to map to OTHER/OTHERS
        if hasattr(enum_class, 'OTHER'):
            return enum_class.OTHER
        elif hasattr(enum_class, 'OTHERS'):
            return enum_class.OTHERS
        return None


def import_survey_excel(file_path, fiscal_year, batch_id):
    """
    Import survey data from Excel file into SurveyResponse table.
    Uses upsert logic to avoid duplicates.
    Properly parses enum fields and handles NULL constraints.
    """
    click.echo(f"\n📊 Importing survey data from Excel...")

    try:
        # Read Excel with header in row 2
        df = pd.read_excel(file_path, header=1, dtype=str)
        click.echo(f"✅ Found {len(df)} rows in Excel file")

        # Clean up column names
        df.columns = [str(col).strip() for col in df.columns]
        click.echo(f"📋 Columns found: {', '.join(df.columns)}")

        # Track statistics including enum parsing
        stats = {
            "created": 0, 
            "updated": 0, 
            "skipped": 0, 
            "errors": 0,
            "enum_parsing": {
                "intermediate_outcome": 0,
                "category": 0,
                "health_care_service": 0,
                "primary": 0,
                "secondary": 0,
                "tertiary": 0,
            }
        }

        click.echo("\n📊 Processing survey responses...")

        for idx, row in df.iterrows():
            try:
                # Skip if budget line is empty
                budget_line = str(row.get("WHAT IS THE BUDGE LINE", "")).strip()
                if (
                    pd.isna(budget_line)
                    or budget_line == ""
                    or budget_line.lower() == "nan"
                ):
                    stats["skipped"] += 1
                    continue

                # Parse ALL enum fields using the _missing_ method
                intermediate_outcome = parse_enum_field(
                    row.get("WHAT INTERMEDIATE OUTCOME DOES THIS BUDGET/PROJECT SPEAK TO", ""),
                    IntermediateOutcome
                )
                if intermediate_outcome:
                    stats["enum_parsing"]["intermediate_outcome"] += 1

                category = parse_enum_field(
                    row.get("CATEGORY", ""),
                    BudgetCategory
                )
                if category:
                    stats["enum_parsing"]["category"] += 1

                health_care_service = parse_enum_field(
                    row.get("HEALTH CARE SERVICE", ""),
                    HealthCareService
                )
                if health_care_service:
                    stats["enum_parsing"]["health_care_service"] += 1

                # Parse primary/secondary/tertiary based on health_care_service
                primary = parse_enum_field(
                    row.get("PRIMARY HEALTH CARE SERVICES", ""),
                    PrimaryHealthService
                )
                if primary:
                    stats["enum_parsing"]["primary"] += 1
                
                secondary = parse_enum_field(
                    row.get("SECONDARY HEALTH CARE SERVICES", ""),
                    SecondaryHealthService
                )
                if secondary:
                    stats["enum_parsing"]["secondary"] += 1
                
                tertiary = parse_enum_field(
                    row.get("TERTIARY HEALTH CARE SERVICES", ""),
                    TertiaryHealthService
                )
                if tertiary:
                    stats["enum_parsing"]["tertiary"] += 1

                # Clean appropriation value
                appropriation = clean_numeric(row.get("What is the Appropriation"))

                # Get MDA and validate it's not null
                mda = str(row.get("What is the MDA", "")).strip()
                if mda.lower() == 'nan':
                    mda = None

                # ✅ FIX: Skip records with NULL MDA to prevent constraint violations
                if not mda:
                    click.echo(f"⚠️  Skipping row {idx + 3}: Missing required field 'MDA'")
                    stats["skipped"] += 1
                    continue

                # Check if response already exists (using no_autoflush to prevent premature flush)
                with db.session.no_autoflush:
                    existing = SurveyResponse.query.filter_by(
                        budget_line=budget_line,
                        mda=mda,
                        fiscal_year=fiscal_year,
                    ).first()

                if existing:
                    # Update existing record with new data
                    existing.responder = str(row.get("Responder", "")).strip()
                    existing.appropriation = appropriation
                    existing.intermediate_outcome = intermediate_outcome
                    existing.category = category
                    existing.health_care_service = health_care_service
                    existing.primary_health_care = primary
                    existing.secondary_health_care = secondary
                    existing.tertiary_health_care = tertiary
                    existing.import_batch = batch_id
                    existing.updated_at = datetime.utcnow()

                    # Re-extract ERGP code in case budget_line changed
                    existing.extracted_ergp_code = SurveyResponse.extract_ergp_code(
                        budget_line
                    )

                    # If it was previously matched, reset match status for re-evaluation
                    if existing.is_matched:
                        existing.is_matched = False
                        existing.matched_at = None

                    stats["updated"] += 1
                else:
                    # Create new response
                    response = SurveyResponse(
                        responder=str(row.get("Responder", "")).strip(),
                        budget_line=budget_line,
                        mda=mda,
                        appropriation=appropriation,
                        intermediate_outcome=intermediate_outcome,
                        category=category,
                        health_care_service=health_care_service,
                        primary_health_care=primary,
                        secondary_health_care=secondary,
                        tertiary_health_care=tertiary,
                        fiscal_year=fiscal_year,
                        import_batch=batch_id,
                    )
                    db.session.add(response)
                    stats["created"] += 1

                # ✅ FIX: Commit every 50 records to minimize data loss on errors
                if (stats["created"] + stats["updated"]) % 50 == 0:
                    try:
                        db.session.commit()
                        click.echo(
                            f"  ⏳ Processed {stats['created'] + stats['updated']} responses..."
                        )
                    except Exception as commit_error:
                        click.echo(f"⚠️  Commit error at batch {stats['created'] + stats['updated']}: {commit_error}", err=True)
                        db.session.rollback()
                        stats["errors"] += 1

            except Exception as e:
                click.echo(f"⚠️  Error at row {idx + 3}: {e}", err=True)
                stats["errors"] += 1
                # Don't rollback - just skip this record and continue
                continue

        # ✅ FIX: CRITICAL - Final commit to save any remaining records
        try:
            db.session.commit()
            click.echo(f"  ✅ Final commit: saved {stats['created'] + stats['updated']} total responses")
        except Exception as e:
            click.echo(f"❌ Final commit failed: {e}", err=True)
            db.session.rollback()
            raise

        # Show summary
        click.echo("\n" + "=" * 50)
        click.echo("📊 SURVEY IMPORT SUMMARY")
        click.echo("=" * 50)
        click.echo(f"✅ Created: {stats['created']}")
        click.echo(f"🔄 Updated: {stats['updated']}")
        click.echo(f"⏭️  Skipped: {stats['skipped']}")
        click.echo(f"⚠️  Errors: {stats['errors']}")
        
        click.echo("\n🔍 ENUM PARSING STATISTICS:")
        click.echo(f"   Intermediate Outcome: {stats['enum_parsing']['intermediate_outcome']}")
        click.echo(f"   Budget Category: {stats['enum_parsing']['category']}")
        click.echo(f"   Health Care Service: {stats['enum_parsing']['health_care_service']}")
        click.echo(f"   Primary Services: {stats['enum_parsing']['primary']}")
        click.echo(f"   Secondary Services: {stats['enum_parsing']['secondary']}")
        click.echo(f"   Tertiary Services: {stats['enum_parsing']['tertiary']}")

        # Show ERGP extraction stats
        total_processed = stats["created"] + stats["updated"]
        if total_processed > 0:
            with_extracted = SurveyResponse.query.filter(
                SurveyResponse.import_batch == batch_id,
                SurveyResponse.extracted_ergp_code.isnot(None),
            ).count()

            click.echo(f"\n🔍 ERGP Code Extraction:")
            click.echo(f"   Extracted: {with_extracted} responses")
            click.echo(f"   Rate: {(with_extracted/total_processed)*100:.1f}%")

    except Exception as e:
        click.echo(f"❌ Failed to import Excel: {e}", err=True)
        db.session.rollback()
        raise

def clean_numeric(value):
    """Clean numeric values from Excel."""
    if pd.isna(value) or value is None:
        return None
    try:
        # Remove commas and spaces, convert to float
        cleaned = str(value).replace(",", "").replace(" ", "")
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


@click.command("match-survey-responses")
@click.option("--batch-id", help="Specific batch to match (optional)")
@click.option("--fiscal-year", default="2024", help="Fiscal year to process")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be matched without committing"
)
@with_appcontext
def match_survey_responses_command(batch_id, fiscal_year, dry_run):
    """
    Match survey responses to projects based on extracted ERGP codes.
    Updates project_id and sets is_matched flag.
    """

    # Build query for unmatched responses
    query = SurveyResponse.query.filter_by(
        is_matched=False, fiscal_year=fiscal_year
    ).filter(SurveyResponse.extracted_ergp_code.isnot(None))

    if batch_id:
        query = query.filter_by(import_batch=batch_id)

    total = query.count()
    if total == 0:
        click.echo("✅ No unmatched responses found!")
        return

    click.echo(f"\n🔍 Found {total} unmatched responses with ERGP codes")

    stats = {"matched": 0, "project_not_found": 0, "already_matched": 0, "errors": 0}

    # Show sample if dry run
    if dry_run:
        samples = query.limit(10).all()
        click.echo("\n📝 Sample responses to match:")
        for resp in samples:
            click.echo(f"  ID {resp.id}: {resp.budget_line[:60]}...")
            click.echo(f"      ERGP: {resp.extracted_ergp_code}")
        return

    # Process in batches
    processed = 0
    offset = 0
    batch_size = 100  # Stream in batches of 100

    while offset < total:
        # Get a batch of responses
        batch = query.limit(batch_size).offset(offset).all()
        for response in batch:
            try:
                # Find project by ERGP code
                # project = Project.query.filter_by(code=response.extracted_ergp_code).first()

                ergp_code = response.extracted_ergp_code
                project = Project.query.filter(
                    (Project.code == ergp_code)
                    | (Project.code == f"ERGP{ergp_code}")  # Some might be uppercase
                ).first()

                # Add logging to see what's happening
                if project:
                    click.echo(f"  ✅ Found project {project.id} for ERGP {ergp_code}")
                else:
                    click.echo(f"  ❌ No project found for ERGP {ergp_code}")

                if project:
                    response.project_id = project.id
                    response.is_matched = True
                    response.matched_at = datetime.utcnow()
                    response.match_method = "auto_extract"
                    stats["matched"] += 1

                else:
                    stats["project_not_found"] += 1

            except Exception as e:
                click.echo(f"⚠️  Error processing response {response.id}: {e}")
                stats["errors"] += 1

            processed += 1

        # Commit after each batch
        db.session.commit()
        click.echo(f"  ⏳ Processed {processed}/{total}...")

        # Move to next batch
        offset += batch_size

        if offset < total:
            time.sleep(0.75)  # Small sleep to avoid overwhelming the database

    # Show summary
    click.echo("\n" + "=" * 50)
    click.echo("📊 MATCHING SUMMARY")
    click.echo("=" * 50)
    click.echo(f"✅ Matched to project: {stats['matched']}")
    click.echo(f"❌ Project not found: {stats['project_not_found']}")
    click.echo(f"⚠️  Errors: {stats['errors']}")

    if stats["matched"] > 0:
        # Show sample matches
        samples = (
            SurveyResponse.query.filter_by(is_matched=True, match_method="auto_extract")
            .order_by(SurveyResponse.matched_at.desc())
            .limit(5)
            .all()
        )

        click.echo("\n📝 Sample matches:")
        for resp in samples:
            click.echo(
                f"  Response {resp.id} → Project {resp.project_id} (ERGP: {resp.extracted_ergp_code})"
            )

    click.echo("=" * 50)


def register_commands(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(import_excel_command)
    app.cli.add_command(clear_data_command)
    app.cli.add_command(list_agencies_command)
    app.cli.add_command(clean_agency_codes_command)
    app.cli.add_command(fetch_survey_data_command)
    app.cli.add_command(match_survey_responses_command)
    app.cli.add_command(init_db_command)
