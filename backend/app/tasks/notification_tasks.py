from celery import shared_task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(bind=True, max_retries=3)
def send_notification_email(self, user_id: str, subject: str, body: str):
    """Send notification email to user"""
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            from app.models.user import User
            from sqlalchemy import select
            
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user or not user.email:
                return {"status": "skipped", "reason": "No email"}
            
            # TODO: Implement actual email sending
            # For now, just log
            print(f"Sending email to {user.email}: {subject}")
            
            return {"status": "sent", "email": user.email}
    
    return asyncio.run(_run())


@shared_task
def process_notification_batch():
    """Process pending notifications"""
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            from app.models.memory import Notification
            from sqlalchemy import select
            
            # Get unread high-priority notifications older than 1 hour
            from datetime import datetime, timedelta
            cutoff = datetime.utcnow() - timedelta(hours=1)
            
            result = await db.execute(
                select(Notification)
                .where(Notification.is_read == False)
                .where(Notification.priority.in_(["high", "critical"]))
                .where(Notification.created_at < cutoff)
                .limit(50)
            )
            notifications = result.scalars().all()
            
            for notif in notifications:
                send_notification_email.delay(
                    str(notif.user_id),
                    notif.title,
                    notif.message or "",
                )
            
            return {"processed": len(notifications)}
    
    return asyncio.run(_run())