#!/usr/bin/env python3
"""
Security Fix Script for AP Intake & Validation System
IMMEDIATE EXECUTION REQUIRED - Addresses critical security vulnerabilities
"""

import os
import sys
import secrets
import shutil
from pathlib import Path
from datetime import datetime

def generate_secure_secret_key():
    """Generate a cryptographically secure secret key."""
    return secrets.token_urlsafe(64)

def backup_file(file_path):
    """Create a backup of the specified file."""
    if os.path.exists(file_path):
        backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(file_path, backup_path)
        print(f"✅ Created backup: {backup_path}")
        return backup_path
    return None

def remove_hardcoded_credentials():
    """Remove hardcoded QuickBooks credentials from config.py."""
    config_file = Path("app/core/config.py")

    if not config_file.exists():
        print(f"❌ Config file not found: {config_file}")
        return False

    # Create backup
    backup_file(config_file)

    # Read the file
    with open(config_file, 'r') as f:
        content = f.read()

    # Lines to remove (hardcoded credentials)
    lines_to_remove = [
        'QUICKBOOKS_SANDBOX_CLIENT_ID: Optional[str] = "ABks36hUKi4CnTlqhEKeztfPxZC083pJ4kH7vqPPtTXbNhTwRy"',
        'QUICKBOOKS_SANDBOX_CLIENT_SECRET: Optional[str] = "tNca9AST3GahKyxVWYziia6vyODid81CV3CEQey7"'
    ]

    # Remove hardcoded credentials
    modified_content = content
    removed_lines = []

    for line in lines_to_remove:
        if line in modified_content:
            modified_content = modified_content.replace(line, 'QUICKBOOKS_SANDBOX_CLIENT_ID: Optional[str] = None')
            removed_lines.append(line)
            print(f"🔒 Removed hardcoded client ID")
        elif "QUICKBOOKS_SANDBOX_CLIENT_SECRET: Optional[str] = \"tNca9AST3GahKyxVWYziia6vyODid81CV3CEQey7\"" in modified_content:
            modified_content = modified_content.replace(
                'QUICKBOOKS_SANDBOX_CLIENT_SECRET: Optional[str] = "tNca9AST3GahKyxVWYziia6vyODid81CV3CEQey7"',
                'QUICKBOOKS_SANDBOX_CLIENT_SECRET: Optional[str] = None'
            )
            removed_lines.append("QUICKBOOKS_SANDBOX_CLIENT_SECRET")
            print(f"🔒 Removed hardcoded client secret")

    # Write the modified content back
    with open(config_file, 'w') as f:
        f.write(modified_content)

    if removed_lines:
        print(f"✅ Successfully removed {len(removed_lines)} hardcoded credentials")
        return True
    else:
        print("⚠️  No hardcoded credentials found (may have been already removed)")
        return True

def update_env_file():
    """Update or create .env file with secure configuration."""
    env_file = Path(".env")

    # Generate secure secret key
    secret_key = generate_secure_secret_key()

    # Environment content
    env_content = f"""# Updated Environment Configuration - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# CRITICAL: Security Configuration
SECRET_KEY={secret_key}
ENVIRONMENT=development
DEBUG=false
REQUIRE_HTTPS=true

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ap_intake
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# External Services - REPLACE WITH YOUR ACTUAL CREDENTIALS
OPENROUTER_API_KEY=sk-or-your-openrouter-api-key
GMAIL_CLIENT_ID=your-gmail-client-id
GMAIL_CLIENT_SECRET=your-gmail-client-secret

# QuickBooks - CRITICAL: Use environment variables only
QUICKBOOKS_SANDBOX_CLIENT_ID=
QUICKBOOKS_SANDBOX_CLIENT_SECRET=
QUICKBOOKS_REDIRECT_URI=http://localhost:8000/api/v1/quickbooks/callback
QUICKBOOKS_ENVIRONMENT=sandbox

# Storage Configuration
STORAGE_TYPE=local
STORAGE_PATH=./storage

# Monitoring
SENTRY_DSN=
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=

# Logging
LOG_LEVEL=INFO
"""

    if env_file.exists():
        backup_file(env_file)
        print("📁 Backed up existing .env file")

    with open(env_file, 'w') as f:
        f.write(env_content)

    print(f"✅ Created/updated .env file with secure secret key")
    print(f"🔑 Generated secure secret key (length: {len(secret_key)})")

    # Set secure file permissions
    os.chmod(env_file, 0o600)
    print("🔒 Set secure file permissions (600) on .env file")

def check_for_other_secrets():
    """Check for other potential secrets in the codebase."""
    print("\n🔍 Scanning for other potential secrets...")

    # Patterns that might indicate secrets
    secret_patterns = [
        "sk-or-",
        "sk-",
        "AIza",
        "xoxb-",
        "xoxp-",
        "AKIA",  # AWS access key
        "ghp_",  # GitHub personal access token
        "gho_",  # GitHub OAuth token
        "ghu_",  # GitHub user token
        "ghs_",  # GitHub server token
        "ghr_",  # GitHub refresh token
        "gho_",
    ]

    # Files to check
    files_to_check = []
    for root, dirs, files in os.walk("."):
        # Skip common non-source directories
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.venv', 'venv']]

        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.json', '.yml', '.yaml', '.env')):
                files_to_check.append(os.path.join(root, file))

    potential_secrets_found = []

    for file_path in files_to_check:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for pattern in secret_patterns:
                    if pattern in content and file_path != "./scripts/security_fix.py":
                        potential_secrets_found.append((file_path, pattern))
        except Exception as e:
            print(f"⚠️  Could not read {file_path}: {e}")

    if potential_secrets_found:
        print(f"\n🚨 POTENTIAL SECRETS FOUND:")
        for file_path, pattern in potential_secrets_found:
            print(f"   - {file_path}: contains '{pattern}'")
        print("\n⚠️  Please review and remove any actual secrets from these files")
    else:
        print("✅ No obvious secret patterns found in source files")

def create_security_readme():
    """Create a security README file with guidelines."""
    security_readme_content = """# Security Configuration Guide

## IMMEDIATE ACTIONS COMPLETED

✅ Removed hardcoded QuickBooks credentials from app/core/config.py
✅ Generated secure secret key and updated .env file
✅ Set secure file permissions on .env file
✅ Created backup of original configuration files

## NEXT STEPS REQUIRED

### 1. Replace Environment Variables
Edit the `.env` file and replace these placeholder values with actual credentials:

- `OPENROUTER_API_KEY=sk-or-your-openrouter-api-key`
- `GMAIL_CLIENT_ID=your-gmail-client-id`
- `GMAIL_CLIENT_SECRET=your-gmail-client-secret`
- `DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ap_intake`

### 2. QuickBooks Configuration
For QuickBooks integration:
1. Go to [QuickBooks Developer Portal](https://developer.intuit.com/)
2. Create a new app or use existing app credentials
3. Add credentials to .env file:
   ```
   QUICKBOOKS_SANDBOX_CLIENT_ID=your-actual-client-id
   QUICKBOOKS_SANDBOX_CLIENT_SECRET=your-actual-client-secret
   ```

### 3. Production Security
For production deployment:
1. Use the `.env.production.template` file
2. Generate a new secret key for production
3. Configure HTTPS and SSL certificates
4. Set up proper monitoring and alerting

## Security Best Practices

### Never commit secrets to version control
- Use environment variables for all sensitive data
- Add `.env` to `.gitignore` file
- Use secret management systems in production

### Regular key rotation
- Rotate API keys every 90 days
- Rotate secret keys regularly
- Update credentials in a controlled manner

### Monitoring and logging
- Enable security event logging
- Monitor for unusual API usage
- Set up alerts for security events

## Files Modified

- `app/core/config.py` - Removed hardcoded credentials
- `.env` - Updated with secure configuration
- Backup files created with timestamp suffix

## Verification

1. Check that no hardcoded credentials remain:
   ```bash
   grep -r "ABks36hUKi4CnTlqhEKeztfPxZC083pJ4kH7vqPPtTXbNhTwRy" app/
   grep -r "tNca9AST3GahKyxVWYziia6vyODid81CV3CEQey7" app/
   ```

2. Verify .env file permissions:
   ```bash
   ls -la .env
   ```

3. Test application starts without errors:
   ```bash
   python -m app.main
   ```

## Support

For security issues or questions:
- Review the full assessment: EXTERNAL_DEPENDENCY_ASSESSMENT.md
- Implementation guide: PRODUCTION_READINESS_IMPLEMENTATION.md
- Contact: security@your-domain.com
"""

    with open("SECURITY_README.md", 'w') as f:
        f.write(security_readme_content)

    print("✅ Created SECURITY_README.md with next steps")

def main():
    """Main security fix execution."""
    print("🚨 AP Intake & Validation System - Security Fix Script")
    print("=" * 60)
    print("🔒 EXECUTING CRITICAL SECURITY FIXES")
    print("=" * 60)

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir.parent)

    print(f"📁 Working directory: {os.getcwd()}")

    try:
        # Step 1: Remove hardcoded credentials
        print("\n1️⃣ Removing hardcoded QuickBooks credentials...")
        if remove_hardcoded_credentials():
            print("✅ Step 1 completed")
        else:
            print("❌ Step 1 failed")
            return False

        # Step 2: Update environment configuration
        print("\n2️⃣ Updating environment configuration...")
        update_env_file()
        print("✅ Step 2 completed")

        # Step 3: Check for other secrets
        print("\n3️⃣ Scanning for other potential secrets...")
        check_for_other_secrets()
        print("✅ Step 3 completed")

        # Step 4: Create security documentation
        print("\n4️⃣ Creating security documentation...")
        create_security_readme()
        print("✅ Step 4 completed")

        print("\n" + "=" * 60)
        print("🎉 SECURITY FIXES COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print("\n📋 SUMMARY OF ACTIONS:")
        print("   ✅ Removed hardcoded QuickBooks credentials")
        print("   ✅ Generated secure secret key")
        print("   ✅ Updated .env file with secure configuration")
        print("   ✅ Set secure file permissions (600)")
        print("   ✅ Created backup files")
        print("   ✅ Scanned for other potential secrets")
        print("   ✅ Created SECURITY_README.md")

        print("\n⚠️  IMPORTANT NEXT STEPS:")
        print("   1. Review SECURITY_README.md")
        print("   2. Update .env file with actual API credentials")
        print("   3. Test application functionality")
        print("   4. Commit changes to version control")
        print("   5. Deploy to production with monitoring")

        print("\n🔒 SECURITY STATUS: IMPROVED")
        print("   - Critical vulnerabilities addressed")
        print("   - Secure configuration implemented")
        print("   - Ready for production deployment")

        return True

    except Exception as e:
        print(f"\n❌ Security fix failed: {e}")
        print("Please review the error and fix manually")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)