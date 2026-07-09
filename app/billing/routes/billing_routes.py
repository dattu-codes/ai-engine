from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.auth.database.connection import get_db
from app.auth.models.auth_models import User
from app.auth.dependencies import get_current_user
from app.config import settings

router = APIRouter(prefix="/billing", tags=["Stripe Billing"])

@router.post("/checkout-session")
def create_checkout_session(
    plan_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a Stripe Checkout Session URL or falls back to a simulated URL if mock key is active."""
    # Stripe Price IDs mapping
    price_id = settings.STRIPE_PRICE_PRO_ID if plan_type.lower() == "pro" else settings.STRIPE_PRICE_ENT_ID
    
    if not settings.STRIPE_SECRET_KEY:
        # Return mock checkout redirect URL
        mock_session_url = f"/billing/mock-activate?plan={plan_type}&token=mock_session_token"
        return {"checkout_url": mock_session_url}
        
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url='http://localhost:8000/dashboard#billing=success',
            cancel_url='http://localhost:8000/dashboard#billing=cancel',
            customer_email=current_user.username + "@example.com" if "@" not in current_user.username else current_user.username,
            metadata={"user_id": str(current_user.id), "plan": plan_type}
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe Session creation failed: {str(e)}")

@router.post("/portal-session")
def create_portal_session(
    current_user: User = Depends(get_current_user)
):
    """Creates a Stripe Customer Portal Redirect URL or falls back to a simulated URL."""
    if not settings.STRIPE_SECRET_KEY or not current_user.stripe_customer_id:
        return {"portal_url": "/dashboard#billing_portal_mock"}
        
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url='http://localhost:8000/dashboard',
        )
        return {"portal_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe Portal Session creation failed: {str(e)}")

@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Processes Stripe Subscription callbacks and updates database plan status."""
    payload = await request.body()
    
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        # Mock callback
        try:
            event = json.loads(payload.decode("utf-8"))
        except Exception:
            return {"status": "ignored"}
    else:
        import stripe
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Stripe Webhook Signature verification failed: {str(e)}")
            
    # Process Stripe Events
    event_type = event.get("type")
    data_obj = event.get("data", {}).get("object", {})
    
    if event_type in ["customer.subscription.created", "customer.subscription.updated"]:
        sub_id = data_obj.get("id")
        cust_id = data_obj.get("customer")
        
        # Read plan from metadata
        metadata = data_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_name = metadata.get("plan", "Pro")
        
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user.stripe_customer_id = cust_id
                user.stripe_subscription_id = sub_id
                user.billing_plan = plan_name
                user.billing_status = "active"
                db.commit()
                
    elif event_type == "customer.subscription.deleted":
        sub_id = data_obj.get("id")
        user = db.query(User).filter(User.stripe_subscription_id == sub_id).first()
        if user:
            user.billing_plan = "Free"
            user.billing_status = "canceled"
            db.commit()
            
    return {"status": "processed"}

@router.get("/mock-activate")
def mock_activate_plan(
    plan: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Convenience endpoint to mock toggle user billing plans for testing."""
    current_user.billing_plan = plan.capitalize()
    current_user.billing_status = "active"
    db.commit()
    
    # Redirect back to frontend
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard#billing=success")
