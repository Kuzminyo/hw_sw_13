import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from src.conf.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, text: str, html: str) -> None:
    """Send a message over SMTP. Runs as a background task, so errors are only logged."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.mail_from_name, settings.mail_from))
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    try:
        if settings.mail_ssl_tls:
            smtp = smtplib.SMTP_SSL(settings.mail_server, settings.mail_port, context=context, timeout=10)
        else:
            smtp = smtplib.SMTP(settings.mail_server, settings.mail_port, timeout=10)
        with smtp:
            if settings.mail_starttls:
                smtp.starttls(context=context)
            if settings.mail_username:
                smtp.login(settings.mail_username, settings.mail_password or "")
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        logger.error("Failed to send email to %s: %s", to, e)


def send_verification_email(email: str, username: str, link: str) -> None:
    send_email(
        to=email,
        subject="Confirm your email",
        text=f"Hi {username}!\n\nConfirm your email by opening this link:\n{link}\n",
        html=(
            f"<p>Hi {escape(username)}!</p>"
            f"<p>Thanks for signing up. Please confirm your email:</p>"
            f'<p><a href="{escape(link)}">Confirm email</a></p>'
        ),
    )


def send_reset_password_email(email: str, username: str, link: str) -> None:
    minutes = settings.reset_token_expire_minutes
    send_email(
        to=email,
        subject="Password reset",
        text=(
            f"Hi {username}!\n\nTo set a new password open this link (valid {minutes} min):\n"
            f"{link}\n\nIf you did not request a reset, just ignore this email.\n"
        ),
        html=(
            f"<p>Hi {escape(username)}!</p>"
            f'<p>To set a new password <a href="{escape(link)}">follow this link</a> '
            f"(valid {minutes} min).</p>"
            f"<p>If you did not request a reset, just ignore this email.</p>"
        ),
    )
