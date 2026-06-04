from decimal import Decimal

from django.db import transaction

from apps.platform.core.application.services.event_service import EventService
from apps.platform.core.models import JournalEntry, JournalLine


class AccountingService:
    def __init__(self, event_service=None):
        self.event_service = event_service or EventService()

    @transaction.atomic
    def post_journal(self, *, tenant, reference_no, lines, entry_date=None, narration="", source_type="", source_id="", user=None):
        total_debit = sum(Decimal(str(line.get("debit", 0))) for line in lines)
        total_credit = sum(Decimal(str(line.get("credit", 0))) for line in lines)
        if total_debit != total_credit:
            raise ValueError("Journal entry must balance debit and credit.")
        journal_data = {
            "tenant": tenant,
            "reference_no": reference_no,
            "status": "posted",
            "narration": narration,
            "source_type": source_type,
            "source_id": source_id,
            "posted_by": user if getattr(user, "is_authenticated", False) else None,
        }
        if entry_date is not None:
            journal_data["entry_date"] = entry_date
        journal = JournalEntry.objects.create(**journal_data)
        for line in lines:
            JournalLine.objects.create(
                journal=journal,
                account=line["account"],
                debit=line.get("debit", 0),
                credit=line.get("credit", 0),
                party_type=line.get("party_type", ""),
                party_id=line.get("party_id", ""),
                metadata=line.get("metadata", {}),
            )
        self.event_service.publish(
            "journal_posted",
            {"journal_id": str(journal.id), "reference_no": reference_no, "source_type": source_type, "source_id": source_id},
            tenant=tenant,
            user=user,
        )
        return journal
