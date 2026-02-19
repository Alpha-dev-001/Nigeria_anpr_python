# Security Policy

##  Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

##  Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow these steps:

### DO NOT create a public GitHub issue

Instead:

1. **Email** the maintainer directly at [kexinlite@gmail.com] with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (if you have them)

2. **Subject Line**: Use `[SECURITY] Brief description of issue`

3. **Response Time**: You can expect an initial response within 48 hours

4. **Disclosure Policy**: 
   - We will investigate and confirm the issue
   - We will develop and test a fix
   - We will release a security patch
   - After the patch is released, we will publicly disclose the vulnerability

### What to Include in Your Report

Please include as much of the following information as possible:

- **Type of vulnerability** (e.g., SQL injection, XSS, authentication bypass)
- **Location** in the codebase where the vulnerability exists
- **Impact** of the vulnerability
- **Steps to reproduce** or proof-of-concept
- **Potential fix** (if you have one)
- Your contact information for follow-up questions

## ️ Security Best Practices

When deploying this system, follow these security guidelines:

### Network Security

- **Do not expose the Flask dashboard to the public internet** without proper authentication
- Run the dashboard behind a firewall or VPN
- If remote access is needed, use:
  - SSH tunneling
  - Reverse proxy with authentication (e.g., nginx with basic auth)
  - VPN connection

### Database Security

- The SQLite database contains vehicle tracking data
- Store `anpr_database.db` in a location with restricted file permissions
- Regularly backup the database
- Consider encrypting the database file if handling sensitive data

### Camera Security

- Use encrypted streams when possible (HTTPS/RTSPS)
- Change default camera passwords
- Isolate cameras on a separate network segment if possible

### Application Security

- Keep all dependencies updated (`pip install --upgrade -r requirements.txt`)
- Run the application with minimal privileges (not as root/admin)
- Monitor system logs for unusual activity
- Set appropriate file permissions on configuration files

### Privacy Considerations

- **Data retention**: Define and implement a data retention policy
- **Consent**: Ensure proper signage and consent for ANPR monitoring
- **Access control**: Limit who can access the dashboard and database
- **Compliance**: Ensure compliance with local privacy laws (NDPR, GDPR, etc.)

##  Known Security Considerations

### Current Limitations

1. **No built-in authentication**: The dashboard has no login system
   - **Mitigation**: Deploy behind authenticated proxy or VPN
   
2. **SQLite database**: Not suitable for high-security deployments
   - **Mitigation**: Consider migrating to PostgreSQL/MySQL for production
   
3. **No encryption at rest**: Database and logs are stored in plaintext
   - **Mitigation**: Use filesystem-level encryption if needed
   
4. **No HTTPS**: Flask runs HTTP only by default
   - **Mitigation**: Use nginx or Apache as reverse proxy with SSL

##  Security Checklist for Production

Before deploying in a production environment:

- [ ] Dashboard is not exposed to public internet
- [ ] Authentication layer added (reverse proxy/VPN)
- [ ] Database has restricted file permissions
- [ ] All dependencies are up to date
- [ ] Camera feeds use encrypted protocols
- [ ] Privacy policy and signage are in place
- [ ] Data retention policy is defined
- [ ] Regular backup strategy is implemented
- [ ] Logs are monitored for suspicious activity
- [ ] Application runs with minimal privileges

##  Security Update Process

When a security issue is patched:

1. Version number is incremented (patch version)
2. Security advisory is published on GitHub
3. CHANGELOG.md is updated
4. Users are notified via:
   - GitHub release notes
   - Repository README
   - Security advisory

##  Contact

For security concerns, contact:
- **Email**: [kexinlite@gmail.com]
- **GitHub**: @Alpha-dev-001

For non-security issues, please use the standard [issue tracker](https://github.com/Alpha-dev-001/Nigeria_anpr_python/issues).

---

**Note**: This is an open-source project intended for educational and research purposes. For production deployments handling sensitive data, consider engaging security professionals for a proper security audit.