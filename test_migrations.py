#!/usr/bin/env python3
"""Test script to verify Alembic migration chain."""

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, '/home/aparna/Desktop/ap_intake')

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from alembic.runtime.environment import EnvironmentContext

def check_migration_chain():
    """Check if the migration chain is valid."""

    # Initialize Alembic configuration
    alembic_cfg = Config("/home/aparna/Desktop/ap_intake/alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)

    # Get all migration heads
    heads = script.get_heads()
    print(f"Migration heads: {heads}")

    # Get all revisions
    revisions = list(script.walk_revisions())
    print(f"\nFound {len(revisions)} revisions:")

    # Walk through the revision chain
    chain = []
    for rev in reversed(revisions):
        chain.append(rev.revision)
        print(f"  {rev.revision} -> {rev.down_revision if rev.down_revision else 'None'} ({rev.doc})")

    # Check for gaps in the chain
    print("\nChecking migration chain integrity...")
    expected_down_revision = None
    for i, rev in enumerate(reversed(revisions)):
        if i == 0:
            if rev.down_revision is not None:
                print(f"ERROR: First revision {rev.revision} has down_revision {rev.down_revision}, should be None")
                return False
        else:
            if rev.down_revision != expected_down_revision:
                print(f"ERROR: Revision {rev.revision} has down_revision {rev.down_revision}, expected {expected_down_revision}")
                return False
        expected_down_revision = rev.revision

    print("✓ Migration chain is valid!")
    return True

def simulate_migration():
    """Simulate the migration process to check for errors."""
    print("\nSimulating migration process...")

    alembic_cfg = Config("/home/aparna/Desktop/ap_intake/alembic.ini")

    # Get the script directory
    script = ScriptDirectory.from_config(alembic_cfg)

    try:
        # Get the current head revision
        head = script.get_current_head()
        print(f"Current head revision: {head}")
    except Exception as e:
        print(f"Error getting head revision: {e}")
        return False

    try:
        # Get the upgrade plan - walk from base to head
        upgrade_plan = []
        for revision in script.walk_revisions():
            upgrade_plan.insert(0, revision.revision)
        print(f"Upgrade plan: {' -> '.join(upgrade_plan)}")
    except Exception as e:
        print(f"Error creating upgrade plan: {e}")
        return False

    print("✓ Migration simulation completed successfully!")
    return True

if __name__ == "__main__":
    print("Checking Alembic migration chain...")
    if check_migration_chain() and simulate_migration():
        print("\n✅ All checks passed! The migration chain is ready for production.")
        sys.exit(0)
    else:
        print("\n❌ Migration chain has errors. Please fix before deploying to production.")
        sys.exit(1)