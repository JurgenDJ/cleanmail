# Security Audit Report - CleanMail

## Executive Summary
This security audit identified several **HIGH** and **MEDIUM** severity issues that should be addressed. 

**Important Context**: This is a local, single-user application where users authenticate with their own email credentials. As such, traditional "unauthorized access" vulnerabilities are less applicable. However, data integrity risks (such as unintended mass deletion) and best practices should still be addressed.

---

## 🔴 CRITICAL VULNERABILITIES

Use IMAP's proper escaping or validate the email address:
```python
# Option 1: Use IMAP's built-in encoding (recommended)
import imaplib
*Note: After review, no critical vulnerabilities were identified for a local, single-user application context.*

---

## 🟠 HIGH SEVERITY VULNERABILITIES

### 1. IMAP Command Injection Leading to Unintended Mass Deletion
**Location:** `mail_client.py:162`  
**Severity:** HIGH (downgraded from CRITICAL for local use)  
**CWE:** CWE-78 (OS Command Injection), CWE-400 (Uncontrolled Resource Consumption)

**Issue:**
```python
_, messages = mail.uid("SEARCH", None, f'FROM "{sender_email}"')
```

The `sender_email` parameter is directly interpolated into an IMAP SEARCH command without sanitization. While this is a local application where users only access their own accounts, there are still risks:

1. **Editable Email Field**: The `st.data_editor()` allows users to edit the Email column (line 53-74 in `main.py`), meaning a user could modify an email address to inject IMAP commands
2. **Unintended Mass Deletion**: A malicious or malformed email address could cause deletion of more emails than intended

**Attack Example:**
If a user edits an email address in the dataframe to: `test@example.com" OR ALL`
The resulting IMAP command would be: `FROM "test@example.com" OR ALL"`
This would match ALL emails in the inbox, not just from that sender.

**Real-World Scenarios:**
- **Accidental Mass Deletion**: User accidentally edits an email address incorrectly, causing unintended deletion of all emails
- **Malicious Email Sender**: An attacker sends an email with a crafted "From" address like `" OR ALL`, which appears in the sender list and could be selected for deletion
- **Data Integrity Risk**: Even though users can only affect their own accounts, this could lead to catastrophic data loss

**Why Not Critical:**
- This is a local application where users authenticate with their own credentials
- Attackers cannot gain access to resources they don't already have access to
- The vulnerability only affects the user's own account
- However, it's still HIGH severity due to potential for unintended mass data loss

**Realistic Attack Scenarios (Local Context):**
1. **User Error**: A user accidentally edits an email address in the dataframe to `" OR ALL`, then selects it for cleanup, causing all emails to be deleted
2. **Malicious Email**: An attacker sends an email with a crafted "From" header like `" OR ALL`, which appears in the sender statistics. If the user selects this sender, it could delete all emails
3. **Data Corruption**: Malformed email headers could result in unexpected email addresses that, when used in the IMAP command, cause unintended behavior

**What This Vulnerability Does NOT Allow:**
- ❌ Access to other users' email accounts (local app, single user)
- ❌ Privilege escalation
- ❌ Access to resources the user doesn't already control
- ❌ Remote code execution on the server

**What This Vulnerability DOES Allow:**
- ✅ Unintended mass deletion of user's own emails
- ✅ Data loss due to malformed IMAP queries
- ✅ Potential for accidental deletion of important emails

**Recommendation:**
# IMAP4.uid() expects the search criteria as a string, but we should escape it properly
# The safest approach is to validate the email format first

# Option 2: Validate and sanitize (more secure)
import re
def validate_email_for_imap(email: str) -> str:
    # Strict email validation
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValueError(f"Invalid email address format: {email}")
    # Check for IMAP injection characters
    if any(char in email for char in ['"', '\\', '\r', '\n']):
        raise ValueError(f"Email address contains invalid characters: {email}")
    return email

# In delete_emails_from_sender:
sender_email = validate_email_for_imap(sender_email)
_, messages = mail.uid("SEARCH", None, f'FROM "{sender_email}"')
```

**Additional Recommendation:**
Make the Email column read-only in the data editor to prevent manual editing:
```python
column_config={
    "Email": st.column_config.TextColumn("Email", disabled=True),  # Make read-only
    # ... other columns
}
```

---

### 2. Credentials Stored in Session State
**Location:** `main.py:119-127, 157-160`  
**Severity:** HIGH  
**CWE:** CWE-312 (Cleartext Storage of Sensitive Information)

**Issue:**
Email addresses and app passwords are stored in Streamlit's `session_state`, which:
- Persists in memory during the session
- Could be exposed through session state inspection
- May be logged or cached by Streamlit
- Survives page refreshes

**Impact:**
- Credential exposure if session state is accessed
- Potential credential leakage in logs
- Security risk if application is compromised

**Recommendation:**
- Use environment variables or secure credential storage
- Implement proper session management
- Clear credentials immediately after use
- Consider using Streamlit secrets management for production

### 3. Unsafe HTML Parsing
**Location:** `mail_client.py:139-140`  
**Severity:** HIGH  
**CWE:** CWE-79 (Cross-site Scripting), CWE-502 (Deserialization of Untrusted Data)

**Issue:**
```python
html_body = part.get_payload(decode=True).decode()
soup = BeautifulSoup(html_body, "html.parser")
```

HTML content from emails is decoded and parsed without:
- Explicit encoding specification (could fail or decode incorrectly)
- Sanitization of malicious content
- Protection against XXE attacks
- Handling of malformed HTML

**Impact:**
- Potential XSS if HTML is rendered elsewhere
- XXE vulnerabilities if XML is processed
- Application crashes on malformed content
- Memory exhaustion with large HTML payloads

**Recommendation:**
```python
# Specify encoding explicitly
html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')

# Use a sanitizer like bleach or html-sanitizer
from bleach import clean
html_body = clean(html_body, tags=[], strip=True)  # Strip all HTML

# Or use BeautifulSoup with safe parser
soup = BeautifulSoup(html_body, "html.parser")  # Already using safe parser, but add size limits
```

### 4. No Input Validation
**Location:** `mail_client.py:12-14, main.py:119-127`  
**Severity:** HIGH  
**CWE:** CWE-20 (Improper Input Validation)

**Issue:**
- Email addresses are not validated before use
- App passwords are not validated
- No length limits on inputs
- No format validation

**Impact:**
- Injection attacks
- Buffer overflows
- Denial of service
- Unexpected application behavior

**Recommendation:**
```python
import re
from email_validator import validate_email, EmailNotValidError

def validate_email_address(email: str) -> str:
    try:
        validation = validate_email(email, check_deliverability=False)
        return validation.email
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email address: {e}")

def validate_app_password(password: str) -> str:
    if not password or len(password) < 8 or len(password) > 100:
        raise ValueError("App password must be between 8 and 100 characters")
    return password
```

---

## 🟡 MEDIUM SEVERITY VULNERABILITIES

### 5. Unsafe Decode Operations
**Location:** `mail_client.py:28, 91, 139, 168`  
**Severity:** MEDIUM  
**CWE:** CWE-172 (Encoding Error)

**Issue:**
Multiple `.decode()` calls without explicit encoding specification:
- `folder.decode()` - Line 28
- `el.decode()` - Line 91
- `part.get_payload(decode=True).decode()` - Line 139
- `b",".join(message_uids).decode("utf-8")` - Line 168 (this one is OK)

**Impact:**
- Encoding errors causing application crashes
- Potential security issues with incorrect encoding
- Inconsistent behavior across systems

**Recommendation:**
Always specify encoding explicitly:
```python
decoded_folder = folder.decode('utf-8', errors='replace')
el.decode('utf-8', errors='replace')
html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
```

### 6. No Rate Limiting
**Location:** `main.py:76-97`  
**Severity:** MEDIUM  
**CWE:** CWE-307 (Improper Restriction of Excessive Authentication Attempts)

**Issue:**
- No rate limiting on email operations
- Users can trigger unlimited email deletions
- No protection against brute force attacks
- No throttling on IMAP connections

**Impact:**
- Denial of service attacks
- Account lockouts from excessive IMAP connections
- Resource exhaustion
- Potential abuse

**Recommendation:**
Implement rate limiting:
```python
from functools import wraps
import time

def rate_limit(max_calls=10, period=60):
    calls = []
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            calls[:] = [c for c in calls if c > now - period]
            if len(calls) >= max_calls:
                raise Exception("Rate limit exceeded")
            calls.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

### 7. Missing Error Handling
**Location:** `mail_client.py:17-44, 60-64`  
**Severity:** MEDIUM  
**CWE:** CWE-703 (Improper Check or Handling of Exceptional Conditions)

**Issue:**
- Generic `Exception` raises without specific error types
- No handling of IMAP connection failures
- No timeout on IMAP operations
- Errors may expose sensitive information

**Impact:**
- Information disclosure through error messages
- Application crashes
- Poor user experience
- Difficult debugging

**Recommendation:**
```python
import imaplib
from imaplib import IMAP4_SSL

class IMAPConnectionError(Exception):
    pass

def connect(self) -> imaplib.IMAP4_SSL:
    try:
        mail = imaplib.IMAP4_SSL(self.__get_imap_url(), timeout=30)
        mail.login(self.email_address, self.app_password)
        return mail
    except imaplib.IMAP4.error as e:
        raise IMAPConnectionError(f"IMAP authentication failed: {str(e)}")
    except Exception as e:
        raise IMAPConnectionError(f"Connection failed: {str(e)}")
```

### 8. No Authentication/Authorization Layer
**Location:** `main.py` (entire file)  
**Severity:** MEDIUM  
**CWE:** CWE-306 (Missing Authentication for Critical Function)

**Issue:**
- No application-level authentication
- Anyone with access to the web interface can use it
- No session management
- No protection against unauthorized access

**Impact:**
- Unauthorized access to email accounts
- Potential abuse of the application
- No audit trail

**Recommendation:**
- Implement application-level authentication
- Add session management
- Implement audit logging
- Consider adding 2FA for sensitive operations

---

## 🟢 LOW SEVERITY / BEST PRACTICES

### 9. Hardcoded IMAP Endpoints
**Location:** `mail_client.py:46-58`  
**Severity:** LOW

**Issue:**
IMAP endpoints are hardcoded, limiting extensibility.

**Recommendation:**
Make endpoints configurable or auto-discoverable.

### 10. No Dependency Vulnerability Scanning
**Location:** `requirements.txt`, `pyproject.toml`  
**Severity:** LOW

**Issue:**
Dependencies may have known vulnerabilities.

**Recommendation:**
- Use `pip-audit` or `safety` to check for known vulnerabilities
- Keep dependencies updated
- Use dependency pinning with security updates

### 11. Dockerfile Security
**Location:** `Dockerfile`  
**Severity:** LOW

**Issue:**
- No non-root user specified
- No security hardening

**Recommendation:**
```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

---

## Summary of Recommendations

### Immediate Actions (High Priority):
1. ✅ Fix IMAP command injection to prevent unintended mass deletion
2. ✅ Make Email column read-only in data editor
3. ✅ Implement input validation for email addresses
4. ✅ Add proper error handling

### Short-term Actions (High Priority):
1. ✅ Secure credential storage
2. ✅ Sanitize HTML parsing
3. ✅ Add rate limiting

### Long-term Actions (Medium Priority):
1. ✅ Implement application-level authentication
2. ✅ Add comprehensive logging
3. ✅ Security hardening of Docker container
4. ✅ Regular dependency vulnerability scanning

---

## Testing Recommendations

1. **Penetration Testing:**
   - Test IMAP injection with various payloads
   - Test input validation with malformed data
   - Test rate limiting and DoS scenarios

2. **Code Review:**
   - Review all user input handling
   - Review all external API calls
   - Review error handling

3. **Security Scanning:**
   - Run static analysis tools (Bandit, Semgrep)
   - Run dependency scanners (pip-audit, safety)
   - Run dynamic analysis tools

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Database](https://cwe.mitre.org/)
- [IMAP Security Best Practices](https://tools.ietf.org/html/rfc3501)
- [Streamlit Security Guide](https://docs.streamlit.io/knowledge-base/deploy/deploy-securely)

