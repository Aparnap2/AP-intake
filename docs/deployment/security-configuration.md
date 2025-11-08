# Security Configuration Guide

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
