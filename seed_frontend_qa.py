"""Seed isolated frontend QA data. Requires LOCAL QA SQLite (run_frontend_qa)."""
from __future__ import annotations

import os
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

for key in (
    "DATABASE_URL",
    "DATABASE_PRIVATE_URL",
    "DATABASE_PUBLIC_URL",
    "PGHOST",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGPORT",
    "RAILWAY_ENVIRONMENT",
):
    os.environ[key] = ""
os.environ["DJANGO_DEBUG"] = "True"
os.environ["DJANGO_HTTPS"] = "False"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homezup.settings")

import homezup.database as dbmod

QA_DB = Path(__file__).resolve().parent / "db_frontend_qa.sqlite3"


def sqlite_database(base_dir: Path) -> dict:
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": QA_DB,
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
    }


dbmod.sqlite_database = sqlite_database  # type: ignore[method-assign]

import django

django.setup()

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone

from fitness.models import (
    ClassSchedule,
    ExpenseCategory,
    FitnessClassType,
    GymExpense,
    GymPayment,
    Membership,
    MembershipPlan,
    Trainer,
    TrainingClass,
    Weekday,
)
from users.models import ClientProfile

FIRST = [
    "Ada", "Bea", "Cam", "Dan", "Eva", "Fay", "Gus", "Hana", "Ian", "Jade",
    "Kai", "Lia", "Max", "Noa", "Oli", "Pia", "Quin", "Rio", "Sam", "Tess",
    "Uma", "Val", "Wes", "Xan", "Yara", "Zed",
]
LAST = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    "India", "Juliet", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa",
    "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey",
    "Xray", "Yankee", "Zulu",
]


def ensure_user(username: str, role: str, *, is_superuser: bool = False) -> User:
    group, _ = Group.objects.get_or_create(name=role)
    password = os.environ.get("HOMEZUP_QA_PASSWORD", "FrontendQa!2026")
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": role,
            "last_name": "QA",
            "email": f"{username}@homezup-qa.local",
            "is_staff": True,
            "is_superuser": is_superuser or role == "Super Admin",
        },
    )
    user.set_password(password)
    user.first_name = role
    user.last_name = "QA"
    user.email = f"{username}@homezup-qa.local"
    user.is_staff = True
    user.is_superuser = is_superuser or role == "Super Admin"
    user.save()
    user.groups.clear()
    user.groups.add(group)
    return user


@transaction.atomic
def seed(member_count: int = 520) -> None:
    print("Environment: LOCAL QA")
    print("Database: SQLite")
    print(f"Database: {QA_DB.name}")

    reception = ensure_user("qa_reception", "Reception")
    admin = ensure_user("qa_admin", "Admin", is_superuser=True)
    print(f"Accounts ready: {reception.username}, {admin.username}")

    plan, _ = MembershipPlan.objects.get_or_create(
        name="QA Monthly 200",
        defaults={
            "duration_months": 1,
            "price": Decimal("200.00"),
            "description": "Frontend QA plan",
            "is_active": True,
        },
    )
    plan.price = Decimal("200.00")
    plan.is_active = True
    plan.save()

    training, _ = TrainingClass.objects.get_or_create(
        name="QA Fitness",
        defaults={
            "class_type": FitnessClassType.MUSCULATION,
            "price_per_member": Decimal("50.00"),
            "is_active": True,
        },
    )

    trainer, _ = Trainer.objects.get_or_create(
        first_name="QA",
        last_name="Coach",
        defaults={
            "specialization": "General",
            "phone": "0611111111",
            "monthly_pay": Decimal("3000.00"),
            "is_active": True,
        },
    )

    ClassSchedule.objects.get_or_create(
        training_class=training,
        weekday=Weekday.MONDAY,
        start_time=time(9, 0),
        end_time=time(10, 0),
        defaults={
            "trainer": trainer,
            "location": "Studio A",
            "is_active": True,
        },
    )

    today = date.today()
    existing = ClientProfile.objects.filter(id_number__startswith="QA").count()
    to_create = max(0, member_count - existing)
    print(f"Existing QA members: {existing}; creating {to_create} more (target {member_count})")

    next_index = existing + 1
    while to_create > 0:
        batch_n = min(100, to_create)
        users = []
        for n in range(batch_n):
            i = next_index + n
            first = FIRST[i % len(FIRST)]
            last = f"{LAST[i % len(LAST)]}{i}"
            user = User(
                username=f"qa_member_{i:04d}",
                first_name=first,
                last_name=last,
                email=f"qa_member_{i:04d}@homezup-qa.local",
            )
            user.set_unusable_password()
            users.append(user)
        User.objects.bulk_create(users)
        created_users = list(
            User.objects.filter(
                username__in=[u.username for u in users]
            ).order_by("username")
        )
        ClientProfile.objects.bulk_create(
            [
                ClientProfile(
                    user=user,
                    phone=f"06{(next_index + n):08d}"[-10:],
                    address=f"{next_index + n} QA Street",
                    city="Casablanca",
                    postal_code="20000",
                    country="Morocco",
                    id_number=f"QA{next_index + n:06d}",
                    is_active=(next_index + n) != 2,
                )
                for n, user in enumerate(created_users)
            ]
        )
        next_index += batch_n
        to_create -= batch_n

    clients = list(
        ClientProfile.objects.filter(id_number__startswith="QA")
        .select_related("user")
        .order_by("id")
    )
    print(f"Total QA clients: {len(clients)}")

    payment_member = clients[0]
    payment_member.is_active = True
    payment_member.user.first_name = "Pay"
    payment_member.user.last_name = "Target"
    payment_member.user.save(update_fields=["first_name", "last_name"])
    payment_member.save(update_fields=["is_active"])

    inactive_member = clients[1] if len(clients) > 1 else None
    if inactive_member:
        inactive_member.is_active = False
        inactive_member.user.first_name = "Inactive"
        inactive_member.user.last_name = "Member"
        inactive_member.user.save(update_fields=["first_name", "last_name"])
        inactive_member.save(update_fields=["is_active"])

    searchable = clients[2] if len(clients) > 2 else payment_member
    searchable.user.first_name = "UniqueSearch"
    searchable.user.last_name = "Zebraqa"
    searchable.user.save(update_fields=["first_name", "last_name"])
    searchable.is_active = True
    searchable.save(update_fields=["is_active"])

    mship, _ = Membership.objects.get_or_create(
        member=payment_member,
        plan=plan,
        start_date=today - timedelta(days=5),
        defaults={
            "end_date": today + timedelta(days=25),
            "price": Decimal("200.00"),
            "notes": "FRONTEND_QA_PAYMENT_TARGET",
        },
    )
    mship.price = Decimal("200.00")
    mship.end_date = today + timedelta(days=25)
    mship.notes = "FRONTEND_QA_PAYMENT_TARGET"
    mship.status_override = ""
    mship.payment_status_override = ""
    mship.save()

    # Ensure remaining == 100 via a single 100 MAD payment (price 200).
    paid = mship.total_paid
    if paid < Decimal("100.00"):
        GymPayment.objects.create(
            membership=mship,
            amount=Decimal("100.00") - paid,
            status="paid",
            payment_method="cash",
            received_by="QA Seed",
            notes="QA seed partial payment",
            idempotency_key="qa-seed-partial-100",
        )
    elif paid > Decimal("100.00"):
        # Reset by deleting extra payments then re-seed one payment of 100.
        mship.payments.all().delete()
        GymPayment.objects.create(
            membership=mship,
            amount=Decimal("100.00"),
            status="paid",
            payment_method="cash",
            received_by="QA Seed",
            notes="QA seed partial payment reset",
            idempotency_key="qa-seed-partial-100-reset",
        )

    mship.refresh_from_db()
    assert mship.remaining_balance == Decimal("100.00"), mship.remaining_balance
    assert mship.total_paid == Decimal("100.00"), mship.total_paid

    search_mship, _ = Membership.objects.get_or_create(
        member=searchable,
        plan=plan,
        start_date=today - timedelta(days=2),
        defaults={
            "end_date": today + timedelta(days=28),
            "price": Decimal("200.00"),
            "notes": "FRONTEND_QA_SEARCH_TARGET",
        },
    )
    if not search_mship.payments.exists():
        GymPayment.objects.create(
            membership=search_mship,
            amount=Decimal("50.00"),
            status="paid",
            payment_method="cash",
            received_by="QA Seed",
            notes="QA search membership",
            idempotency_key="qa-seed-search-50",
        )

    extra = []
    for idx, client in enumerate(clients[3:80]):
        if Membership.objects.filter(member=client, plan=plan).exists():
            continue
        extra.append(
            Membership(
                member=client,
                plan=plan,
                start_date=today - timedelta(days=idx % 20),
                end_date=today + timedelta(days=30 - (idx % 10)),
                price=Decimal("200.00"),
                notes="QA_SEED",
            )
        )
    Membership.objects.bulk_create(extra, ignore_conflicts=True)

    now = timezone.now()
    GymExpense.objects.get_or_create(
        category=ExpenseCategory.RENT,
        title="QA Rent",
        year=now.year,
        month=now.month,
        defaults={"amount": Decimal("1500.00"), "notes": "Frontend QA"},
    )

    print("Payment target membership id:", mship.id)
    print("Payment member id:", payment_member.id)
    print("Search member id:", searchable.id)
    print("Inactive member id:", inactive_member.id if inactive_member else None)
    print("Inactive qr present:", bool(inactive_member.qr_token) if inactive_member else False)
    print("Trainer id:", trainer.id)
    print("Class id:", training.id)
    print("Active member count:", ClientProfile.objects.filter(is_active=True).count())
    print("Total member count:", ClientProfile.objects.count())
    print("SEED_OK")


if __name__ == "__main__":
    count = int(os.environ.get("HOMEZUP_QA_MEMBER_COUNT", "520"))
    seed(count)
