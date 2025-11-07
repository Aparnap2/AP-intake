#!/usr/bin/env python3
"""
Initialize default export templates in the database.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_db
from app.models.export_models import ExportTemplate, ExportFormat
from app.services.export_template_service import ExportTemplateService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_export_templates():
    """Initialize default export templates."""
    logger.info("Initializing default export templates...")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Check if templates already exist
            existing_templates = db.query(ExportTemplate).count()
            logger.info(f"Found {existing_templates} existing export templates")

            # Create template service
            template_service = ExportTemplateService(db)

            # Create default templates
            created_templates = template_service.create_default_templates()
            logger.info(f"Created {len(created_templates)} default export templates")

            # List all templates
            all_templates = db.query(ExportTemplate).all()
            logger.info("Available export templates:")
            for template in all_templates:
                status = "Active" if template.is_active else "Inactive"
                logger.info(f"  - {template.name} ({template.format.value}) - {status} - Usage: {template.usage_count}")

        except Exception as e:
            logger.error(f"Error creating export templates: {e}")
            db.rollback()
            raise

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)


def list_templates():
    """List all export templates."""
    logger.info("Listing export templates...")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            templates = db.query(ExportTemplate).order_by(ExportTemplate.format, ExportTemplate.name).all()

            if not templates:
                logger.info("No export templates found")
                return

            logger.info("Export Templates:")
            current_format = None

            for template in templates:
                if template.format != current_format:
                    current_format = template.format
                    logger.info(f"\n{current_format.value.upper()} Templates:")
                    logger.info("-" * 50)

                status = "✓ Active" if template.is_active else "✗ Inactive"
                usage_info = f"Used {template.usage_count} times"
                if template.last_used_at:
                    usage_info += f" (last: {template.last_used_at.strftime('%Y-%m-%d')})"

                logger.info(f"  {template.name}")
                logger.info(f"    Status: {status}")
                logger.info(f"    Usage: {usage_info}")
                logger.info(f"    Fields: {len(template.field_mappings)} mappings")
                if template.description:
                    logger.info(f"    Description: {template.description}")
                logger.info("")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        sys.exit(1)


def delete_template(template_name: str):
    """Delete an export template by name."""
    logger.info(f"Deleting export template: {template_name}")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            template = db.query(ExportTemplate).filter(ExportTemplate.name == template_name).first()
            if not template:
                logger.error(f"Template '{template_name}' not found")
                sys.exit(1)

            # Check if template is in use
            from app.models.export_models import ExportJob
            active_jobs = db.query(ExportJob).filter(
                ExportJob.template_id == template.id,
                ExportJob.status.in_(['pending', 'preparing', 'processing'])
            ).count()

            if active_jobs > 0:
                logger.error(f"Cannot delete template '{template_name}' - {active_jobs} active jobs")
                sys.exit(1)

            db.delete(template)
            db.commit()
            logger.info(f"Successfully deleted template: {template_name}")

        except Exception as e:
            logger.error(f"Error deleting template: {e}")
            db.rollback()
            sys.exit(1)

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)


def activate_template(template_name: str):
    """Activate an export template."""
    logger.info(f"Activating export template: {template_name}")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            template = db.query(ExportTemplate).filter(ExportTemplate.name == template_name).first()
            if not template:
                logger.error(f"Template '{template_name}' not found")
                sys.exit(1)

            template.is_active = True
            db.commit()
            logger.info(f"Successfully activated template: {template_name}")

        except Exception as e:
            logger.error(f"Error activating template: {e}")
            db.rollback()
            sys.exit(1)

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)


def deactivate_template(template_name: str):
    """Deactivate an export template."""
    logger.info(f"Deactivating export template: {template_name}")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            template = db.query(ExportTemplate).filter(ExportTemplate.name == template_name).first()
            if not template:
                logger.error(f"Template '{template_name}' not found")
                sys.exit(1)

            template.is_active = False
            db.commit()
            logger.info(f"Successfully deactivated template: {template_name}")

        except Exception as e:
            logger.error(f"Error deactivating template: {e}")
            db.rollback()
            sys.exit(1)

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python init_export_templates.py <command> [args]")
        print("\nCommands:")
        print("  init                 Initialize default export templates")
        print("  list                 List all export templates")
        print("  delete <name>        Delete a template by name")
        print("  activate <name>      Activate a template")
        print("  deactivate <name>    Deactivate a template")
        print("\nExamples:")
        print("  python init_export_templates.py init")
        print("  python init_export_templates.py list")
        print("  python init_export_templates.py delete 'Old Template'")
        print("  python init_export_templates.py activate 'Standard CSV Export'")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        init_export_templates()
    elif command == "list":
        list_templates()
    elif command == "delete":
        if len(sys.argv) < 3:
            print("Error: Template name required for delete command")
            sys.exit(1)
        delete_template(sys.argv[2])
    elif command == "activate":
        if len(sys.argv) < 3:
            print("Error: Template name required for activate command")
            sys.exit(1)
        activate_template(sys.argv[2])
    elif command == "deactivate":
        if len(sys.argv) < 3:
            print("Error: Template name required for deactivate command")
            sys.exit(1)
        deactivate_template(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()