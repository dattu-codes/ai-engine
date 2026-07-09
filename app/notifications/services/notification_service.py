import logging
import smtplib
from email.mime.text import MIMEText
from sqlalchemy.orm import Session
from app.auth.models.auth_models import User, NotificationPreference
from app.config import settings

logger = logging.getLogger("notification_service")

# Global notifications cache list for in-memory testing/verification
sent_notifications_log = []

class NotificationService:
    @staticmethod
    def get_or_create_preferences(db: Session, user_id: int) -> NotificationPreference:
        """Returns the user's notification preferences, creating defaults if not present."""
        prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        if not prefs:
            prefs = NotificationPreference(
                user_id=user_id,
                email_analysis_completed=True,
                email_fix_completed=True,
                email_tests_completed=True,
                email_repo_synced=True,
                email_invitation_accepted=True,
                email_deployment_completed=True
            )
            db.add(prefs)
            db.commit()
            db.refresh(prefs)
        return prefs

    @classmethod
    def send_notification(
        cls,
        db: Session,
        user_id: int,
        event_type: str,
        subject: str,
        body: str
    ) -> bool:
        """
        Sends an email notification if the user's preferences permit.
        Supported event_types:
          - analysis_completed
          - fix_completed
          - tests_completed
          - repo_synced
          - invitation_accepted
          - deployment_completed
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"Failed to send notification: User {user_id} not found.")
            return False
            
        prefs = cls.get_or_create_preferences(db, user_id)
        
        # Check specific preference flag
        preference_map = {
            "analysis_completed": prefs.email_analysis_completed,
            "fix_completed": prefs.email_fix_completed,
            "tests_completed": prefs.email_tests_completed,
            "repo_synced": prefs.email_repo_synced,
            "invitation_accepted": prefs.email_invitation_accepted,
            "deployment_completed": prefs.email_deployment_completed
        }
        
        is_enabled = preference_map.get(event_type, True)
        if not is_enabled:
            logger.info(f"Notification suppressed for User {user_id} on event '{event_type}' by preference.")
            return False
            
        recipient = user.username + "@example.com" if "@" not in user.username else user.username
        
        # Log to in-memory validation queue
        notification_record = {
            "user_id": user_id,
            "email": recipient,
            "event_type": event_type,
            "subject": subject,
            "body": body
        }
        sent_notifications_log.append(notification_record)
        logger.info(f"[NOTIFY] Event: {event_type} | To: {recipient} | Subject: {subject}")
        
        # If SMTP is configured, attempt sending live email (catch exceptions gracefully)
        if settings.SMTP_USER or settings.SMTP_PASSWORD:
            try:
                msg = MIMEText(body)
                msg["Subject"] = subject
                msg["From"] = settings.SMTP_FROM
                msg["To"] = recipient
                
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
                    if settings.SMTP_USER and settings.SMTP_PASSWORD:
                        server.starttls()
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
                logger.info(f"Live SMTP email sent successfully to {recipient}")
            except Exception as e:
                logger.error(f"Failed to send live SMTP email to {recipient}: {e}")
                
        return True
