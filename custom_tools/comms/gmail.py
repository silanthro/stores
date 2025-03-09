import os
import smtplib
from email.mime.text import MIMEText


def send_email_via_gmail(subject: str, body: str, recipients: list[str]) -> None:
    """
    Send an email via Gmail to a list of recipients
    Args:
    - subject (str): Subject header of email
    - body (str): Contents of email
    - recipients (list[str]): Recipients as a list of email addresses
    """
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_PASSWORD").replace(" ", "")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
        smtp_server.login(sender, password)
        smtp_server.sendmail(
            from_addr=sender,
            to_addrs=recipients,
            msg=msg.as_string(),
        )
