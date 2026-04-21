"""Ad-hoc helper: print every admin/owner/founder user with their quota +
subscription state. Safe to run against live DB (reads only)."""
import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.identity import User
from app.models.financial import UserQuota, Subscription


async def main() -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(User.role.in_(("FOUNDER", "OWNER", "ADMIN"))).limit(5)
        )
        users = result.scalars().all()
        for u in users:
            print(f"User: {u.email} | role: {u.role} | tenant: {u.tenant_id}")
            qr = await db.execute(select(UserQuota).where(UserQuota.user_id == u.id))
            q = qr.scalar_one_or_none()
            if q:
                print(
                    f"  Quota plan={q.plan_tier} "
                    f"monthly=${float(q.monthly_credit_usd):.2f} "
                    f"spent=${float(q.spend_this_month_usd):.4f} "
                    f"daily={q.daily_credit_usd} "
                    f"overage={q.overage_action}"
                )
            else:
                print("  (no quota row yet)")
            sr = await db.execute(
                select(Subscription).where(Subscription.tenant_id == u.tenant_id)
            )
            for s in sr.scalars().all():
                print(
                    f"  Sub plan={s.plan} status={s.status} "
                    f"spent=${float(s.spend_this_month_usd):.4f}"
                )


if __name__ == "__main__":
    asyncio.run(main())
