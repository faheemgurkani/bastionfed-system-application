"""SMTP email sender for BastionFed transactional messages.

Reads connection details from config:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME.

If any required setting is missing, ``send_client_credentials`` raises ``RuntimeError``
with a clear message so the API can surface it to the admin.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    from app.config import settings
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def send_client_credentials(
    *,
    to_email: str,
    node_name: str,
    login_url: str,
    username: str,
    password: str,
    tenant_name: str,
) -> None:
    """Send a credentials email to a newly provisioned person-client.

    Raises:
        RuntimeError: if SMTP is not configured.
        smtplib.SMTPException: on delivery failure.
    """
    from app.config import settings

    if not _smtp_configured():
        raise RuntimeError(
            "SMTP is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD "
            "to enable automatic credential delivery."
        )

    from_email = settings.smtp_from_email or settings.smtp_user
    from_header = f"{settings.smtp_from_name} <{from_email}>"
    subject = f"Your BastionFed Access Credentials — {tenant_name}"

    body_text = f"""\
Hello,

You have been granted access to the BastionFed Security Operations Center
as a client/site user for: {node_name}

Sign in at: {login_url}

Your credentials
  Username / Email: {username}
  Password:         {password}

After signing in, you will see only the data associated with your site.
Keep these credentials secure and do not share them.

If you did not expect this message, please contact your administrator.

— {settings.smtp_from_name}
"""

    body_html = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f4f4f5;color:#111;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 16px;">
    <tr><td align="center">
      <table width="100%" style="max-width:520px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:#000;padding:28px 32px;">
            <p style="margin:0;font-size:11px;font-family:monospace;letter-spacing:0.15em;text-transform:uppercase;color:#555;">BastionFed SOC</p>
            <h1 style="margin:8px 0 0;font-size:20px;font-weight:700;color:#fff;">Your Access Credentials</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px 8px;">
            <p style="margin:0 0 16px;font-size:14px;line-height:1.6;color:#333;">
              You have been granted access to the BastionFed Security Operations Center
              as a <strong>client / site user</strong> for:
            </p>
            <div style="background:#f8f8f8;border:1px solid #e4e4e7;border-radius:8px;padding:12px 16px;margin-bottom:20px;">
              <p style="margin:0;font-size:13px;font-family:monospace;color:#111;">{node_name}</p>
            </div>
            <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#111;">Sign in at:</p>
            <a href="{login_url}" style="display:inline-block;margin-bottom:20px;font-size:13px;color:#0070f3;word-break:break-all;">{login_url}</a>
            <table width="100%" style="background:#f8f8f8;border:1px solid #e4e4e7;border-radius:8px;padding:0;border-collapse:collapse;">
              <tr>
                <td style="padding:12px 16px 6px;font-size:11px;font-family:monospace;letter-spacing:0.1em;text-transform:uppercase;color:#888;">Username / Email</td>
              </tr>
              <tr>
                <td style="padding:0 16px 12px;font-size:14px;font-family:monospace;color:#111;">{username}</td>
              </tr>
              <tr>
                <td style="padding:12px 16px 6px;border-top:1px solid #e4e4e7;font-size:11px;font-family:monospace;letter-spacing:0.1em;text-transform:uppercase;color:#888;">Password</td>
              </tr>
              <tr>
                <td style="padding:0 16px 12px;font-size:14px;font-family:monospace;color:#111;">{password}</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px 28px;">
            <p style="margin:0;font-size:12px;line-height:1.6;color:#888;">
              After signing in, you will see only the data associated with your site.
              Keep these credentials secure and do not share them.<br/><br/>
              If you did not expect this message, please contact your administrator.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#f8f8f8;border-top:1px solid #e4e4e7;padding:16px 32px;text-align:center;">
            <p style="margin:0;font-size:11px;color:#aaa;">&copy; {tenant_name} &mdash; Powered by BastionFed</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(str(settings.smtp_user), str(settings.smtp_password))
            server.sendmail(str(from_email), to_email, msg.as_string())
        logger.info("Credentials email sent to %s", to_email)
    except smtplib.SMTPException:
        logger.exception("Failed to send credentials email to %s", to_email)
        raise
