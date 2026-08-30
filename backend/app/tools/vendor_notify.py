from app.config import settings
from app.database import SyncSessionLocal
from app.models import VendorCommunication
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def send_proactive_advisory(supplier_id: int, supplier_email: str, subject: str, body: str) -> dict:
    """
    Sends a proactive advisory email to a vendor (e.g., asking to dispatch early due to traffic).
    Logs the communication in the database.
    """
    
    # 1. Log to database
    with SyncSessionLocal() as session:
        comm = VendorCommunication(
            supplier_id=supplier_id,
            communication_type="proactive_advisory",
            subject=subject,
            body=body,
            status="SENT"
        )
        session.add(comm)
        session.commit()
        session.refresh(comm)
        comm_id = comm.comm_id
        
    # 2. Send email via SendGrid (or Mock)
    email_text = f"""
    ================= PROACTIVE ADVISORY (ID: {comm_id}) =================
    To: {supplier_email}
    From: {settings.SENDGRID_FROM_EMAIL}
    Subject: {subject}
    
    {body}
    
    Thank you,
    Autonomous FMCG Supply Chain System
    ======================================================================
    """
    
    if settings.SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            
            message = Mail(
                from_email=settings.SENDGRID_FROM_EMAIL,
                to_emails=supplier_email,
                subject=subject,
                plain_text_content=email_text)
                
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            logger.info(f"SendGrid advisory dispatched. Status: {response.status_code}")
            return {"status": "success", "provider": "sendgrid", "comm_id": comm_id}
        except Exception as e:
            logger.error(f"Failed to send advisory via SendGrid: {str(e)}")
            return {"status": "error", "error": str(e), "comm_id": comm_id}
    else:
        # Mock mode
        logger.info(f"\n[MOCK ADVISORY DISPATCH]\n{email_text}")
        return {"status": "success", "provider": "mock", "comm_id": comm_id}
