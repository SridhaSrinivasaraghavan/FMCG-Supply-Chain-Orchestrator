from app.config import settings
import logging

logger = logging.getLogger(__name__)

def send_purchase_order_email(supplier_email: str, po_details: dict) -> dict:
    """
    Sends an automated purchase order email via SendGrid.
    If SENDGRID_API_KEY is not set, falls back to a console mock (for demo/testing).
    """
    po_id = po_details.get("po_id", "UNKNOWN")
    material_name = po_details.get("material_name", "Material")
    quantity = po_details.get("quantity", 0.0)
    total_cost = po_details.get("total_cost", 0.0)
    
    email_body = f"""
    ================= PURCHASE ORDER {po_id} =================
    To: {supplier_email}
    From: {settings.SENDGRID_FROM_EMAIL}
    Subject: URGENT: Purchase Order #{po_id} for {material_name}
    
    Dear Supplier,
    
    Due to a supply chain disruption, we are placing an emergency 
    expedited order for the following items:
    
    - Material: {material_name}
    - Quantity: {quantity} units
    - Total Approved Cost: ${total_cost:.2f}
    
    Please confirm receipt and expected delivery date immediately.
    
    Thank you,
    Autonomous FMCG Supply Chain System
    =========================================================
    """
    
    if settings.SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            
            message = Mail(
                from_email=settings.SENDGRID_FROM_EMAIL,
                to_emails=supplier_email,
                subject=f"URGENT: Purchase Order #{po_id} for {material_name}",
                plain_text_content=email_body)
                
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            logger.info(f"SendGrid email dispatched. Status code: {response.status_code}")
            return {"status": "success", "provider": "sendgrid"}
        except Exception as e:
            logger.error(f"Failed to send email via SendGrid: {str(e)}")
            return {"status": "error", "error": str(e)}
    else:
        # Mock mode
        logger.info(f"\n[MOCK EMAIL DISPATCH]\n{email_body}")
        return {"status": "success", "provider": "mock"}
