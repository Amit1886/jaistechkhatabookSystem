from __future__ import annotations

from decimal import Decimal, InvalidOperation
import os

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SyncMapping, SyncedInvoice, SyncedObject


def _extract_token(auth_header: str | None) -> str:
    if not auth_header:
        return ""
    auth_header = auth_header.strip()
    if auth_header.lower().startswith("token "):
        return auth_header[6:].strip()
    return auth_header


class InvoiceSyncAPI(APIView):
    """
    Token-protected cloud endpoint that accepts invoice payloads from desktop clients.

    Desktop client sends: Authorization: Token <CLOUD_API_TOKEN>
    Cloud server verifies: SYNC_API_TOKEN (set in cloud .env)
    """

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        expected = (os.getenv("SYNC_API_TOKEN") or "").strip()
        provided = _extract_token(request.headers.get("Authorization"))

        if not expected or provided != expected:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        if isinstance(data, list):
            results = []
            for row in data:
                res = self._upsert_one(row)
                if res[0] is None:
                    return Response(res[1], status=res[2])
                results.append(res[0])
            return Response({"ok": True, "results": results}, status=status.HTTP_200_OK)

        obj, err, code = self._upsert_one(data)
        if obj is None:
            return Response(err, status=code)
        return Response({"ok": True, **obj}, status=status.HTTP_200_OK)

    def _upsert_one(self, payload):
        if not isinstance(payload, dict):
            return None, {"detail": "Invalid payload"}, status.HTTP_400_BAD_REQUEST

        number = (payload.get("number") or "").strip()
        if not number:
            return None, {"detail": "Missing invoice number"}, status.HTTP_400_BAD_REQUEST

        obj, created = SyncedInvoice.objects.update_or_create(
            number=number,
            defaults={"payload": payload},
        )
        return {"number": obj.number, "created": created}, None, None


def _mapping_get(*, device_id: str, model_name: str, local_id: str) -> str:
    try:
        row = SyncMapping.objects.filter(device_id=device_id, model_name=model_name, local_id=local_id).only("cloud_id").first()
        return (row.cloud_id or "") if row else ""
    except Exception:
        return ""


def _mapping_set(*, device_id: str, model_name: str, local_id: str, cloud_id: str) -> None:
    try:
        SyncMapping.objects.update_or_create(
            device_id=device_id,
            model_name=model_name,
            local_id=local_id,
            defaults={"cloud_id": str(cloud_id)},
        )
    except Exception:
        # Best-effort; even if mapping fails, keep the inbox row.
        return


def _payload_fields(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {}
    fields = payload.get("fields")
    if isinstance(fields, dict):
        return fields
    # Backward-compatible: accept flattened payloads.
    return payload


def _payload_relations(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {}
    rel = payload.get("relations")
    return rel if isinstance(rel, dict) else {}


def _safe_decimal(value: object, *, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _safe_int(value: object, *, default: int = 0, min_value: int | None = None) -> int:
    try:
        num = int(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        num = int(default)
    if min_value is not None:
        num = max(int(min_value), num)
    return num


def _resolve_owner_user(*, device_id: str, relations: dict, fields: dict):
    try:
        from django.contrib.auth import get_user_model  # noqa: WPS433

        User = get_user_model()
    except Exception:
        return None

    owner_user = None
    owner_rel = relations.get("owner") if isinstance(relations, dict) else None
    if isinstance(owner_rel, dict):
        owner_local = str(owner_rel.get("local_id") or "").strip()
        if owner_local:
            owner_cloud = _mapping_get(device_id=device_id, model_name=str(owner_rel.get("model") or "accounts.User"), local_id=owner_local)
            if owner_cloud:
                owner_user = User.objects.filter(pk=owner_cloud).first()

    if owner_user is None:
        owner_email = (fields.get("owner_email") or "").strip().lower()
        if owner_email:
            owner_user = User.objects.filter(email=owner_email).first()

    return owner_user


def _apply_accounts_user(*, device_id: str, local_id: str, action: str, payload: object) -> tuple[bool, str, str]:
    """
    Apply accounts.User create/update/delete to the cloud DB.

    Returns: (ok, status, message)
    """
    try:
        from django.contrib.auth import get_user_model  # noqa: WPS433

        User = get_user_model()
    except Exception as e:  # pragma: no cover
        return False, "error", f"User model not available: {e}"

    fields = _payload_fields(payload)
    email = (fields.get("email") or "").strip().lower()
    if not email:
        return False, "error", "Missing email"

    try:
        user = User.objects.filter(email=email).first()
        if action == "delete":
            if user:
                user.is_active = False
                user.save(update_fields=["is_active"])
                _mapping_set(device_id=device_id, model_name="accounts.User", local_id=local_id, cloud_id=str(user.pk))
            return True, "applied", "deactivated"

        created = False
        if not user:
            user = User(email=email)
            try:
                user.set_unusable_password()
            except Exception:
                pass
            created = True

        # Never allow desktop sync to grant elevated permissions on cloud.
        user.is_staff = False
        user.is_superuser = False

        username = (fields.get("username") or "").strip()
        if username:
            user.username = username
        mobile = (fields.get("mobile") or "").strip()
        if mobile:
            user.mobile = mobile

        # Verification/status flags (best-effort, safe defaults).
        for flag in ("email_verified", "mobile_verified", "is_social_login", "is_otp_verified"):
            if flag in fields:
                try:
                    setattr(user, flag, bool(fields.get(flag)))
                except Exception:
                    pass

        if "is_active" in fields:
            try:
                user.is_active = bool(fields.get("is_active"))
            except Exception:
                user.is_active = True
        else:
            user.is_active = True

        user.save()
        _mapping_set(device_id=device_id, model_name="accounts.User", local_id=local_id, cloud_id=str(user.pk))
        return True, "applied", "created" if created else "updated"
    except Exception as e:
        return False, "error", f"User apply failed: {e}"


def _apply_khataapp_party(*, device_id: str, local_id: str, action: str, payload: object) -> tuple[bool, str, str]:
    try:
        from khataapp.models import Party  # noqa: WPS433
        from django.contrib.auth import get_user_model  # noqa: WPS433

        User = get_user_model()
    except Exception as e:  # pragma: no cover
        return False, "error", f"Party model not available: {e}"

    fields = _payload_fields(payload)
    relations = _payload_relations(payload)

    owner_user = None
    owner_rel = relations.get("owner") if isinstance(relations, dict) else None
    if isinstance(owner_rel, dict):
        owner_local = str(owner_rel.get("local_id") or "").strip()
        if owner_local:
            owner_cloud = _mapping_get(device_id=device_id, model_name=str(owner_rel.get("model") or "accounts.User"), local_id=owner_local)
            if owner_cloud:
                owner_user = User.objects.filter(pk=owner_cloud).first()
    if owner_user is None:
        owner_email = (fields.get("owner_email") or "").strip().lower()
        if owner_email:
            owner_user = User.objects.filter(email=owner_email).first()

    try:
        cloud_id = _mapping_get(device_id=device_id, model_name="khataapp.Party", local_id=local_id)
        party = Party.objects.filter(pk=cloud_id).first() if cloud_id else None

        if action == "delete":
            if party:
                # Soft-delete to preserve history.
                if hasattr(party, "is_active"):
                    party.is_active = False
                    party.save(update_fields=["is_active"])
                else:
                    party.delete()
            return True, "applied", "deleted"

        created = False
        if party is None:
            party = Party()
            created = True

        if owner_user is not None:
            party.owner = owner_user

        # Basic fields (best-effort, only set if present in payload).
        for key in (
            "name",
            "mobile",
            "email",
            "gst",
            "address",
            "party_type",
            "upi_id",
            "bank_account_number",
            "is_premium",
            "whatsapp_number",
            "sms_number",
            "credit_grade",
            "credit_period",
            "opening_balance",
            "is_active",
            "customer_category",
        ):
            if key in fields:
                try:
                    setattr(party, key, fields.get(key))
                except Exception:
                    pass

        party.save()
        _mapping_set(device_id=device_id, model_name="khataapp.Party", local_id=local_id, cloud_id=str(party.pk))
        return True, "applied", "created" if created else "updated"
    except Exception as e:
        return False, "error", f"Party apply failed: {e}"


def _apply_khataapp_transaction(*, device_id: str, local_id: str, action: str, payload: object) -> tuple[bool, str, str]:
    try:
        from khataapp.models import Transaction  # noqa: WPS433
        from khataapp.models import Party  # noqa: WPS433
    except Exception as e:  # pragma: no cover
        return False, "error", f"Transaction model not available: {e}"

    fields = _payload_fields(payload)
    relations = _payload_relations(payload)

    party_rel = relations.get("party") if isinstance(relations, dict) else None
    party_cloud_id = ""
    if isinstance(party_rel, dict):
        party_local = str(party_rel.get("local_id") or "").strip()
        if party_local:
            party_cloud_id = _mapping_get(device_id=device_id, model_name=str(party_rel.get("model") or "khataapp.Party"), local_id=party_local)
    if not party_cloud_id and action != "delete":
        return False, "pending_dependency", "Missing party mapping"

    try:
        cloud_id = _mapping_get(device_id=device_id, model_name="khataapp.Transaction", local_id=local_id)
        txn = Transaction.objects.filter(pk=cloud_id).first() if cloud_id else None

        if action == "delete":
            if txn:
                if hasattr(txn, "is_deleted"):
                    txn.is_deleted = True
                    if hasattr(txn, "deleted_at") and not txn.deleted_at:
                        from django.utils import timezone  # noqa: WPS433

                        txn.deleted_at = timezone.now()
                    txn.save(update_fields=["is_deleted", "deleted_at"] if hasattr(txn, "deleted_at") else ["is_deleted"])
                else:
                    txn.delete()
            return True, "applied", "deleted"

        created = False
        if txn is None:
            txn = Transaction()
            created = True

        try:
            txn.party = Party.objects.get(pk=party_cloud_id)
        except Party.DoesNotExist:
            return False, "pending_dependency", "Party not found on cloud yet"

        for key in (
            "txn_type",
            "txn_mode",
            "amount",
            "date",
            "notes",
            "gst_type",
            "is_deleted",
            "deleted_at",
        ):
            if key in fields:
                try:
                    setattr(txn, key, fields.get(key))
                except Exception:
                    pass

        # Optional links (best-effort). If mapping isn't present yet, keep NULL.
        optional_relations = {
            "order": "commerce.Order",
            "payment": "commerce.Payment",
            "voucher": "commerce.SalesVoucher",
            "invoice": "commerce.Invoice",
        }
        for field_name, default_model in optional_relations.items():
            rel = relations.get(field_name)
            if not isinstance(rel, dict):
                continue
            rel_local = str(rel.get("local_id") or "").strip()
            if not rel_local:
                continue
            rel_model = str(rel.get("model") or default_model)
            mapped = _mapping_get(device_id=device_id, model_name=rel_model, local_id=rel_local)
            if not mapped:
                continue
            try:
                setattr(txn, f"{field_name}_id", mapped)
            except Exception:
                pass

        txn.save()
        _mapping_set(device_id=device_id, model_name="khataapp.Transaction", local_id=local_id, cloud_id=str(txn.pk))
        return True, "applied", "created" if created else "updated"
    except Exception as e:
        return False, "error", f"Transaction apply failed: {e}"


def _apply_commerce_category(*, device_id: str, local_id: str, action: str, payload: object) -> tuple[bool, str, str]:
    try:
        from commerce.models import Category  # noqa: WPS433
    except Exception as e:  # pragma: no cover
        return False, "error", f"Category model not available: {e}"

    fields = _payload_fields(payload)
    relations = _payload_relations(payload)
    owner_user = _resolve_owner_user(device_id=device_id, relations=relations, fields=fields)
    if owner_user is None:
        return True, "pending_dependency", "Owner not available yet"

    try:
        cloud_id = _mapping_get(device_id=device_id, model_name="commerce.Category", local_id=local_id)
        category = Category.objects.filter(pk=cloud_id).first() if cloud_id else None

        if action == "delete":
            if category:
                category.delete()
            return True, "applied", "deleted"

        name = (fields.get("name") or "").strip()
        if not name:
            return False, "error", "Missing name"

        description = fields.get("description")
        description = str(description) if description is not None else ""

        created = False
        if category is None:
            # Best-effort de-dupe: owner + name
            category = Category.objects.filter(owner=owner_user, name__iexact=name).first()
        if category is None:
            category = Category(owner=owner_user)
            created = True

        category.owner = owner_user
        category.name = name
        category.description = description
        category.save()

        _mapping_set(device_id=device_id, model_name="commerce.Category", local_id=local_id, cloud_id=str(category.pk))
        return True, "applied", "created" if created else "updated"
    except Exception as e:
        return False, "error", f"Category apply failed: {e}"


def _apply_commerce_product(*, device_id: str, local_id: str, action: str, payload: object) -> tuple[bool, str, str]:
    try:
        from commerce.models import Category, Product  # noqa: WPS433
    except Exception as e:  # pragma: no cover
        return False, "error", f"Product model not available: {e}"

    fields = _payload_fields(payload)
    relations = _payload_relations(payload)
    owner_user = _resolve_owner_user(device_id=device_id, relations=relations, fields=fields)
    if owner_user is None:
        return True, "pending_dependency", "Owner not available yet"

    sku = (fields.get("sku") or "").strip()
    if not sku:
        return False, "error", "Missing sku"

    # Resolve category mapping (if present in payload).
    category_obj = None
    category_rel = relations.get("category") if isinstance(relations, dict) else None
    if isinstance(category_rel, dict):
        cat_local = str(category_rel.get("local_id") or "").strip()
        if cat_local:
            cat_cloud = _mapping_get(
                device_id=device_id,
                model_name=str(category_rel.get("model") or "commerce.Category"),
                local_id=cat_local,
            )
            if not cat_cloud:
                return True, "pending_dependency", "Category not available yet"
            category_obj = Category.objects.filter(pk=cat_cloud).first()

    try:
        cloud_id = _mapping_get(device_id=device_id, model_name="commerce.Product", local_id=local_id)
        product = Product.objects.filter(pk=cloud_id).first() if cloud_id else None

        if action == "delete":
            if product:
                product.delete()
            return True, "applied", "deleted"

        created = False
        if product is None:
            existing = Product.objects.filter(sku=sku).first()
            if existing:
                if existing.owner and existing.owner != owner_user:
                    return False, "error", f"SKU already used by another account ({sku})"
                product = existing
            else:
                product = Product(sku=sku)
                created = True

        # Apply fields (best-effort).
        if "name" in fields:
            name = str(fields.get("name") or "").strip()
            if name:
                product.name = name
        if "price" in fields:
            product.price = _safe_decimal(fields.get("price"), default=_safe_decimal(getattr(product, "price", 0) or 0))
        if "stock" in fields:
            product.stock = _safe_int(fields.get("stock"), default=getattr(product, "stock", 0) or 0, min_value=0)
        if "min_stock" in fields:
            product.min_stock = _safe_int(fields.get("min_stock"), default=getattr(product, "min_stock", 0) or 0, min_value=0)
        if "description" in fields:
            desc = fields.get("description")
            product.description = str(desc) if desc is not None else ""
        if "unit" in fields and (fields.get("unit") or ""):
            unit = str(fields.get("unit") or "").strip()
            if unit:
                product.unit = unit
        if "hsn_code" in fields:
            hsn = (fields.get("hsn_code") or "").strip()
            product.hsn_code = hsn or None
        if "gst_rate" in fields:
            product.gst_rate = _safe_decimal(fields.get("gst_rate"), default=_safe_decimal(getattr(product, "gst_rate", 0) or 0))

        # Owner + SKU are authoritative.
        product.owner = owner_user
        product.sku = sku

        if category_rel is not None:
            product.category = category_obj

        product.save()
        _mapping_set(device_id=device_id, model_name="commerce.Product", local_id=local_id, cloud_id=str(product.pk))
        return True, "applied", "created" if created else "updated"
    except Exception as e:
        return False, "error", f"Product apply failed: {e}"


class ObjectSyncAPI(APIView):
    """
    Generic Desktop -> Cloud sync endpoint.

    Desktop client sends a list of sync events (create/update/delete) and the cloud
    stores them in `commerce.SyncedObject`. Selected core models are also applied
    into the cloud DB using `commerce.SyncMapping` for idempotency.
    """

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        expected = (os.getenv("SYNC_API_TOKEN") or "").strip()
        provided = _extract_token(request.headers.get("Authorization"))

        if not expected or provided != expected:
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        rows = data if isinstance(data, list) else [data]

        results: list[dict] = []
        for row in rows:
            results.append(self._process_one(row))

        return Response({"ok": True, "results": results}, status=status.HTTP_200_OK)

    def _process_one(self, row) -> dict:
        if not isinstance(row, dict):
            return {"ok": False, "status": "error", "error": "Invalid payload"}

        device_id = str(row.get("device_id") or "").strip()
        model_name = str(row.get("model") or row.get("model_name") or "").strip()
        local_id = str(row.get("local_id") or row.get("object_id") or "").strip()
        action = str(row.get("action") or "").strip().lower()
        payload = row.get("payload") if "payload" in row else {}

        if not device_id or not model_name or not local_id or action not in {"create", "update", "delete"}:
            return {
                "ok": False,
                "status": "error",
                "model": model_name,
                "local_id": local_id,
                "error": "Missing required fields",
            }

        # Store/update the inbox row first (always).
        try:
            SyncedObject.objects.update_or_create(
                device_id=device_id,
                model_name=model_name,
                local_id=local_id,
                defaults={"action": action, "payload": payload},
            )
        except Exception as e:
            return {"ok": False, "status": "error", "model": model_name, "local_id": local_id, "error": f"Inbox save failed: {e}"}

        # Apply core models into cloud DB (best-effort).
        appliers = {
            "accounts.User": _apply_accounts_user,
            "khataapp.Party": _apply_khataapp_party,
            "khataapp.Transaction": _apply_khataapp_transaction,
            "commerce.Category": _apply_commerce_category,
            "commerce.Product": _apply_commerce_product,
        }

        apply_fn = appliers.get(model_name)
        if not apply_fn:
            return {"ok": True, "status": "stored", "model": model_name, "local_id": local_id}

        ok, apply_status, msg = apply_fn(device_id=device_id, local_id=local_id, action=action, payload=payload)
        return {"ok": bool(ok), "status": apply_status, "model": model_name, "local_id": local_id, "message": msg}
