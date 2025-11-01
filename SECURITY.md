# Security Policy

## Supported Versions

We actively maintain and provide security updates for the following versions of CorreX:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Considerations

### API Key Security

CorreX stores your Google Gemini API key in the local `config.json` file. Please be aware:

- **Never commit your `config.json` to version control** - the `.gitignore` file is configured to exclude it
- **Never share your API key publicly** - treat it like a password
- **Store config.json securely** - ensure proper file permissions on your system
- **Rotate keys regularly** - periodically generate new API keys in Google AI Studio
- **Use environment variables** - for production deployments, consider using environment variables instead

### Data Privacy

CorreX processes text in the following ways:

- **Local Processing**: Keystroke buffering and clipboard operations happen entirely on your machine
- **Cloud Processing**: Text is sent to Google's Gemini API for correction/dictation
- **No Telemetry**: CorreX does not collect or transmit usage analytics
- **No Storage**: Corrected text is not stored by CorreX (only in local history database)

### Windows Security

CorreX requires elevated permissions for:

- **Keyboard Hooks**: To capture global hotkeys across all applications
- **Clipboard Access**: To read and write text for correction operations
- **UI Automation**: To interact with active windows using pywinauto

These permissions are inherent to the functionality and cannot be reduced without breaking core features.

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in CorreX, please report it responsibly:

### How to Report

1. **Do NOT create a public issue** - this could put users at risk
2. **Email the maintainers** or use GitHub's private vulnerability reporting feature
3. **Include detailed information**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)
   - Your contact information (optional)

### What to Expect

- **Acknowledgment**: We'll acknowledge receipt within 48 hours
- **Assessment**: We'll assess the severity and impact within 7 days
- **Fix Timeline**: 
  - Critical vulnerabilities: 1-3 days
  - High severity: 1-2 weeks
  - Medium/Low severity: 2-4 weeks
- **Disclosure**: We'll coordinate with you on public disclosure timing
- **Credit**: You'll be credited in the CHANGELOG (unless you prefer anonymity)

### Severity Levels

#### Critical
- Remote code execution
- API key exposure in logs/outputs
- Privilege escalation vulnerabilities

#### High
- Unauthorized data access
- Injection vulnerabilities (command, SQL, etc.)
- Authentication bypass

#### Medium
- Information disclosure
- Denial of service
- Insecure defaults

#### Low
- Minor information leaks
- Best practice violations

## Security Best Practices for Users

### Configuration
- Use strong, unique API keys
- Review candidates before adding to config
- Disable unused features
- Keep configuration file backed up securely

### Updates
- Always use the latest version of CorreX
- Subscribe to release notifications
- Review CHANGELOG for security fixes
- Update dependencies regularly:
  ```powershell
  pip install --upgrade correx
  ```

### Monitoring
- Enable logging to detect anomalies:
  ```powershell
  correx --verbose --log-file logs/correx.log
  ```
- Review logs periodically for suspicious activity
- Monitor API usage in Google AI Studio

### Network Security
- Use CorreX only on trusted networks
- Consider firewall rules if running in corporate environments
- Be aware that API calls transmit text over the internet (HTTPS)

## Known Security Limitations

### Current Design Constraints
1. **Global Keyboard Hooks**: Required for system-wide functionality, but could theoretically be used as a keylogger
2. **Clipboard Access**: CorreX temporarily uses clipboard for text injection (though never stores clipboard history)
3. **Plain Text Config**: API keys stored in plain text (consider using Windows Credential Manager in future versions)
4. **No Encryption**: Text sent to Gemini API is encrypted in transit (HTTPS) but not end-to-end encrypted

### Mitigation Strategies
- **Open Source**: Code is fully auditable
- **No Network Access Beyond Gemini**: CorreX only communicates with Google's API
- **Local Processing**: Buffer and history operations are entirely local
- **User Control**: All features can be disabled in configuration

## Security Roadmap

Future versions may include:

- [ ] Windows Credential Manager integration for API key storage
- [ ] Encrypted local history database
- [ ] Optional local-only mode (no API calls)
- [ ] Audit logging for sensitive operations
- [ ] Configurable permissions model
- [ ] Integration with Windows Security Center

## Third-Party Dependencies

CorreX relies on several third-party libraries. We monitor for security advisories affecting:

- `google-generativeai` - Google's official Gemini SDK
- `keyboard` - Keyboard hook library
- `pywinauto` - Windows automation library
- `SpeechRecognition` - Voice recognition library
- Other dependencies listed in `requirements.txt`

To check for vulnerable dependencies:
```powershell
pip install safety
safety check -r correX/requirements.txt
```

## Responsible Disclosure Timeline

We follow a 90-day disclosure timeline:

1. **Day 0**: Vulnerability reported
2. **Day 7**: Assessment completed, fix development begins
3. **Day 30**: Fix released in patch version
4. **Day 90**: Full public disclosure (if not disclosed earlier)

Critical vulnerabilities may have accelerated timelines.

## Security Champions

If you're interested in helping improve CorreX's security posture:

- Review code for security issues
- Propose security enhancements
- Update this policy with best practices
- Help triage security reports

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

**Last Updated**: November 2025  
**Version**: 1.0.0  
**Contact**: Via GitHub Issues (for non-sensitive matters)
