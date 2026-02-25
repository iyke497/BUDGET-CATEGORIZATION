# fmoh2024/models.py
import re
from datetime import datetime

from fmoh2024.extensions import db


class Project(db.Model):
    """Stores the approved 2024 budget projects with GIFMIS codes for exact matching."""

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)  # ERGP Code - no longer unique

    # Project details
    project_name = db.Column(db.Text)
    project_status = db.Column(db.String(100))
    appropriation = db.Column(db.Numeric(20, 2))

    # ===== ENHANCED: GIFMIS CODING SYSTEM =====
    ministry_code = db.Column(db.String(10), nullable=True)
    ministry_name = db.Column(db.String(250))

    agency_code = db.Column(db.String(12), nullable=True)  # May be null
    agency_name = db.Column(db.String(250))

    # ===== RELATIONSHIP (for direct access to agency) =====
    # This creates a foreign key relationship to MinistryAgency
    agency_id = db.Column(
        db.Integer,
        db.ForeignKey("ministry_agencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Normalized fields for fuzzy matching (backup)
    agency_normalized = db.Column(db.String(250))

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Composite unique constraint: code + agency (project uniqueness)
    __table_args__ = (
        # Ensure unique projects per agency
        db.UniqueConstraint("code", "agency_id", name="uix_code_agency"),
        # Keep the composite index for code + COALESCE(agency_code, 'NULL') for backward compatibility
        db.Index(
            "idx_unique_ergp_agency",
            code,
            db.func.coalesce(agency_code, "NULL"),
            unique=True,
        ),
        db.Index("idx_agency_code", "agency_code"),
        db.Index("idx_ministry_code", "ministry_code"),
        db.Index("idx_code_ministry", "code", "ministry_code"),
        db.Index("idx_agency_id", "agency_id"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-populate agency_id if possible
        if not self.agency_id and self.agency_code:
            agency = MinistryAgency.query.filter_by(
                agency_code=self.agency_code, is_active=True
            ).first()
            if agency:
                self.agency_id = agency.id

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "project_name": self.project_name,
            "project_status": self.project_status,
            "appropriation": float(self.appropriation) if self.appropriation else None,
            "ministry_code": self.ministry_code,
            "ministry_name": self.ministry_name,
            "agency_code": self.agency_code,
            "agency_name": self.agency_name,
            "agency_id": self.agency_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_categorization(self):
        """Get the most recent survey categorization for this project."""
        if not self.survey_responses:
            return None

        # Return the most recent matched response
        latest = (
            self.survey_responses.filter_by(is_matched=True)
            .order_by(SurveyResponse.import_date.desc())
            .first()
        )

        return latest


class MinistryAgency(db.Model):
    """Normalized reference table for ministries and their agencies from GIFMIS coding system"""

    __tablename__ = "ministry_agencies"

    id = db.Column(db.Integer, primary_key=True)

    # ===== GIFMIS CODING SYSTEM =====
    ministry_code = db.Column(db.String(10), nullable=False, index=True)
    agency_code = db.Column(db.String(12), unique=True, nullable=False, index=True)

    # ===== OFFICIAL NAMES =====
    agency_name = db.Column(db.String(300), nullable=False)
    ministry_name = db.Column(db.String(300), nullable=False)

    # ===== NORMALIZED NAMES FOR MATCHING =====
    agency_name_normalized = db.Column(db.String(300), index=True)
    ministry_name_normalized = db.Column(db.String(300), index=True)

    # ===== HIERARCHY INFORMATION =====
    is_self_accounting = db.Column(
        db.Boolean, default=False
    )  # Agencies that are also ministries
    is_parastatal = db.Column(db.Boolean, default=False)

    # ===== METADATA =====
    is_active = db.Column(db.Boolean, default=True)
    fiscal_year = db.Column(
        db.String(4), default="2024"
    )  # For versioning by fiscal year

    # ===== RELATIONSHIPS =====
    # One ministry/agency can have many projects
    projects = db.relationship(
        "Project",
        backref="ministry_agency",
        foreign_keys="Project.agency_code",
        primaryjoin="MinistryAgency.agency_code == Project.agency_code",
        lazy="dynamic",
    )

    # ===== AUDIT =====
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ===== INDEXES =====
    __table_args__ = (
        db.Index("idx_ministry_agency", "ministry_code", "agency_code"),
        db.Index("idx_agency_name_search", "agency_name_normalized"),
        db.Index("idx_ministry_search", "ministry_name_normalized"),
        db.Index("idx_fiscal_year", "fiscal_year", "is_active"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-generate normalized names if not provided
        if not self.agency_name_normalized and self.agency_name:
            self.agency_name_normalized = self.normalize_name(self.agency_name)
        if not self.ministry_name_normalized and self.ministry_name:
            self.ministry_name_normalized = self.normalize_name(self.ministry_name)

        # Auto-detect if agency is self-accounting (ministry equals agency)
        if self.agency_name == self.ministry_name:
            self.is_self_accounting = True

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalization for FMOH Budget Data:
        1. Uppercase and strip whitespace.
        2. Replace '&' with 'AND'.
        3. Remove all punctuation/special characters (except spaces).
        4. Collapse multiple internal spaces into one.
        """
        if not name or not isinstance(name, str):
            return ""

        # 1. Basic cleaning & Replace '&'
        normalized = name.upper().strip()
        normalized = normalized.replace("&", " AND ")

        # 2. Remove all punctuation (Keep only A-Z and 0-9)
        # [^A-Z0-9 ] means: "Find anything that is NOT a letter, number, or space"
        normalized = re.sub(r"[^A-Z0-9 ]", "", normalized)

        # 3. Collapse multiple spaces (e.g., "BUDGET   CAT" -> "BUDGET CAT")
        normalized = " ".join(normalized.split())

        return normalized

    def to_dict(self):
        return {
            "id": self.id,
            "ministry_code": self.ministry_code,
            "agency_code": self.agency_code,
            "agency_name": self.agency_name,
            "ministry_name": self.ministry_name,
            "agency_name_normalized": self.agency_name_normalized,
            "ministry_name_normalized": self.ministry_name_normalized,
            "is_self_accounting": self.is_self_accounting,
            "is_parastatal": self.is_parastatal,
            "is_active": self.is_active,
            "fiscal_year": self.fiscal_year,
            "project_count": self.projects.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def find_agency_by_name(cls, name, threshold=0.85):
        """Fuzzy find agency by name with similarity threshold"""
        from difflib import SequenceMatcher

        normalized_search = cls.normalize_name(name)

        # First try exact match on normalized name
        exact_match = cls.query.filter(
            cls.agency_name_normalized == normalized_search, cls.is_active == True
        ).first()

        if exact_match:
            return exact_match

        # Fall back to fuzzy matching
        all_agencies = cls.query.filter(cls.is_active == True).all()
        best_match = None
        best_score = 0

        for agency in all_agencies:
            score = SequenceMatcher(
                None, normalized_search, agency.agency_name_normalized
            ).ratio()

            if score > best_score and score >= threshold:
                best_score = score
                best_match = agency

        return best_match

    @classmethod
    def get_agencies_by_ministry(cls, ministry_code=None, ministry_name=None):
        """Get all agencies under a ministry"""
        query = cls.query.filter(cls.is_active == True)

        if ministry_code:
            query = query.filter(cls.ministry_code == ministry_code)
        elif ministry_name:
            normalized = cls.normalize_name(ministry_name)
            query = query.filter(cls.ministry_name_normalized == normalized)

        return query.order_by(cls.agency_name).all()

    @classmethod
    def get_ministry_hierarchy(cls):
        """Get hierarchical structure of ministries and their agencies"""
        ministries = {}

        # Get all active records
        records = (
            cls.query.filter(cls.is_active == True)
            .order_by(cls.ministry_code, cls.agency_code)
            .all()
        )

        for record in records:
            ministry_key = f"{record.ministry_code}|{record.ministry_name}"

            if ministry_key not in ministries:
                ministries[ministry_key] = {
                    "ministry_code": record.ministry_code,
                    "ministry_name": record.ministry_name,
                    "agencies": [],
                }

            ministries[ministry_key]["agencies"].append(
                {
                    "agency_code": record.agency_code,
                    "agency_name": record.agency_name,
                    "is_self_accounting": record.is_self_accounting,
                    "is_parastatal": record.is_parastatal,
                }
            )

        return list(ministries.values())


class SurveyResponse(db.Model):
    """Stores raw survey responses about budget projects for categorization."""

    __tablename__ = "survey_responses"

    id = db.Column(db.Integer, primary_key=True)

    # ===== RESPONDENT INFORMATION =====
    responder = db.Column(db.String(200), nullable=True, index=True)

    # ===== BUDGET PROJECT REFERENCE (contains ERGP code) =====
    budget_line = db.Column(db.Text, nullable=False)  # "WHAT IS THE BUDGE LINE"

    # ===== MDA (Ministry/Department/Agency) =====
    mda = db.Column(db.String(300), nullable=False, index=True)  # "What is the MDA"

    # ===== BUDGET AMOUNT =====
    appropriation = db.Column(
        db.Numeric(20, 2), nullable=True
    )  # "What is the Appropriation"

    # ===== OUTCOME CLASSIFICATION =====
    intermediate_outcome = db.Column(
        db.Text, nullable=True
    )  # "WHAT INTERMEDIATE OUTCOME DOES THIS BUDGET/PROJECT SPEAK TO"

    # ===== HEALTH CATEGORIZATION =====
    category = db.Column(db.String(200), nullable=True, index=True)  # "CATEGORY"
    health_care_service = db.Column(db.Text, nullable=True)  # "HEALTH CARE SERVICE"
    primary_health_care = db.Column(
        db.Text, nullable=True
    )  # "PRIMARY HEALTH CARE SERVICES"
    secondary_health_care = db.Column(
        db.Text, nullable=True
    )  # "SECONDARY HEALTH CARE SERVICES"
    tertiary_health_care = db.Column(
        db.Text, nullable=True
    )  # "TERTIARY HEALTH CARE SERVICES"

    # ===== NORMALIZED FIELDS FOR EXTRACTION =====
    # We'll store the extracted ERGP code for faster querying
    extracted_ergp_code = db.Column(db.String(50), nullable=True, index=True)

    # ===== FOREIGN KEY TO PROJECT =====
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ===== RELATIONSHIP =====
    # This creates the bidirectional link
    project = db.relationship(
        "Project",
        backref=db.backref("survey_responses", lazy="dynamic", cascade="save-update"),
    )

    # ===== METADATA =====
    fiscal_year = db.Column(db.String(4), default="2024", index=True)
    import_batch = db.Column(db.String(50), nullable=True, index=True)
    import_date = db.Column(db.DateTime, default=datetime.utcnow)

    # ===== MATCHING STATUS =====
    is_matched = db.Column(db.Boolean, default=False, index=True)
    matched_at = db.Column(db.DateTime, nullable=True)
    match_method = db.Column(
        db.String(50), nullable=True
    )  # 'auto_extract', 'manual', etc.

    # ===== AUDIT =====
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ===== INDEXES FOR PERFORMANCE =====
    __table_args__ = (
        db.Index("idx_survey_unmatched", "is_matched", "fiscal_year"),
        db.Index("idx_survey_batch", "import_batch", "is_matched"),
        db.Index("idx_survey_ergp_lookup", "extracted_ergp_code", "is_matched"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-extract ERGP code when budget_line is set
        if self.budget_line and not self.extracted_ergp_code:
            self.extracted_ergp_code = self.extract_ergp_code(self.budget_line)

    @staticmethod
    def extract_ergp_code(budget_line):
        """
        Extract ERGP code from budget line text.
        Expected format: "description-ergp12345678" or similar
        """
        if not budget_line or not isinstance(budget_line, str):
            return None

        import re

        # Pattern 1: Look for 'ergp' followed by numbers (case insensitive)
        match = re.search(r"ergp[_-]?(\d+)", budget_line.lower())
        if match:
            return match.group(1)

        # Pattern 2: Look for numbers at the end (if no ergp prefix)
        match = re.search(r"(\d+)$", budget_line.strip())
        if match:
            return match.group(1)

        # Pattern 3: Look for any 8+ digit number (ERGP codes are typically long)
        match = re.search(r"(\d{8,})", budget_line)
        if match:
            return match.group(1)

        return None

    def match_to_project(self):
        """
        Attempt to match this survey response to a project
        based on extracted ERGP code.
        """
        if not self.extracted_ergp_code:
            self.extracted_ergp_code = self.extract_ergp_code(self.budget_line)
            if not self.extracted_ergp_code:
                return None

        project = Project.query.filter_by(code=self.extracted_ergp_code).first()

        if project:
            self.project_id = project.id
            self.is_matched = True
            self.matched_at = datetime.utcnow()
            self.match_method = "auto_extract"

        return project

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "responder": self.responder,
            "budget_line": self.budget_line,
            "extracted_ergp_code": self.extracted_ergp_code,
            "mda": self.mda,
            "appropriation": float(self.appropriation) if self.appropriation else None,
            "intermediate_outcome": self.intermediate_outcome,
            "category": self.category,
            "health_care_service": self.health_care_service,
            "primary_health_care": self.primary_health_care,
            "secondary_health_care": self.secondary_health_care,
            "tertiary_health_care": self.tertiary_health_care,
            "project_id": self.project_id,
            "fiscal_year": self.fiscal_year,
            "is_matched": self.is_matched,
            "matched_at": self.matched_at.isoformat() if self.matched_at else None,
            "import_batch": self.import_batch,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<SurveyResponse {self.id}: {self.budget_line[:50]}...>"
