from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from order_engine.catalog import MenuCatalog
from order_engine.config_loader import RestaurantConfigBundle
from order_engine.models import OrderResultStatus
from order_engine.order_service import OrderService
from order_engine.parity import check_order_parity
from order_engine.results import AddItemResult, OperationResult

from apps.order_api.db.order_store import OrderRecord, OrderStore, _day_bounds_utc, normalize_phone
from apps.order_api.db.payment_store import PaymentStore
from apps.order_api.db.session_store import SessionStore
from apps.order_api.db.sms_store import SmsStore
from apps.order_api.integrations import charge_payment, send_order_sms
from apps.order_api.schemas import OrderListItem, PaymentCaptureResponse, ToolResponse
from apps.order_api.settings import get_settings
from apps.order_api.store_hours import delivery_available, is_store_open
from apps.payment_service.schemas import ChargeRequest
from apps.sms_gateway.schemas import SendSmsRequest


class CallOrderUseCases:
    """Application layer — orchestrates domain service, sessions, and orders."""

    def __init__(self) -> None:
        self._sessions: dict[str, OrderService] = {}
        self._config_cache: dict[str, RestaurantConfigBundle] = {}
        self._session_store = SessionStore()
        self._order_store = OrderStore()
        self._payment_store = PaymentStore()
        self._sms_store = SmsStore()
        self._active_order_ids: dict[str, uuid.UUID] = {}
        self._memory_orders: dict[uuid.UUID, OrderRecord] = {}
        self._memory_caller_phones: dict[str, str] = {}

    def store_status(self, restaurant_id: str) -> dict:
        bundle = self.get_bundle(restaurant_id)
        open_now, open_msg = is_store_open(bundle.operations)
        delivery_ok, delivery_msg = delivery_available(bundle.operations)
        escalation = bundle.operations.get("contact_channels", {}).get("escalation_staff_phone")
        return {
            "is_open": open_now,
            "message": open_msg,
            "delivery_available": delivery_ok,
            "delivery_message": delivery_msg,
            "escalation_phone": escalation,
        }

    async def _get_order_record(self, order_id: uuid.UUID) -> OrderRecord | None:
        record = await self._order_store.get_order(order_id)
        if record is not None:
            return record
        return self._memory_orders.get(order_id)

    def _closed_result(self, service: OrderService, message: str) -> ToolResponse:
        result = OperationResult(
            status=OrderResultStatus.STORE_CLOSED,
            message=message,
            cart=service.cart,
        )
        return self.build_response(service, result)

    def _ensure_store_open(self, restaurant_id: str, service: OrderService) -> ToolResponse | None:
        if not get_settings().enforce_store_hours:
            return None
        open_now, msg = is_store_open(self.get_bundle(restaurant_id).operations)
        if not open_now:
            return self._closed_result(service, msg)
        return None

    async def _resolve_customer_phone(
        self, restaurant_id: str, call_id: str, explicit: str = ""
    ) -> str | None:
        if explicit:
            return normalize_phone(explicit)
        key = self._session_key(restaurant_id, call_id)
        if key in self._memory_caller_phones:
            return self._memory_caller_phones[key]
        db_phone = await self._session_store.get_caller_phone(restaurant_id, call_id)
        return db_phone

    async def start_call(self, restaurant_id: str, call_id: str, caller_phone: str = "") -> dict:
        bundle = self.get_bundle(restaurant_id)
        await self._session_store.ensure_restaurant(
            restaurant_id, str(bundle.menu.get("name", restaurant_id))
        )
        if caller_phone:
            phone = normalize_phone(caller_phone)
            key = self._session_key(restaurant_id, call_id)
            self._memory_caller_phones[key] = phone
            await self._session_store.set_caller_phone(restaurant_id, call_id, phone)
        status = self.store_status(restaurant_id)
        return {"call_id": call_id, "restaurant_id": restaurant_id, **status}

    def config_root(self) -> Path:
        return Path(__file__).resolve().parents[2] / "config" / "restaurants"

    def config_dir(self, restaurant_id: str) -> Path:
        path = self.config_root() / restaurant_id
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Restaurant '{restaurant_id}' not found")
        return path

    def _config_dir(self, restaurant_id: str) -> Path:
        return self.config_dir(restaurant_id)

    def _session_key(self, restaurant_id: str, call_id: str) -> str:
        return f"{restaurant_id}:{call_id}"

    def get_bundle(self, restaurant_id: str) -> RestaurantConfigBundle:
        if restaurant_id not in self._config_cache:
            self._config_cache[restaurant_id] = RestaurantConfigBundle.load(
                self._config_dir(restaurant_id)
            )
        return self._config_cache[restaurant_id]

    async def get_service(self, restaurant_id: str, call_id: str) -> OrderService:
        key = self._session_key(restaurant_id, call_id)
        if key not in self._sessions:
            catalog = MenuCatalog.from_path(self._config_dir(restaurant_id))
            bundle = self.get_bundle(restaurant_id)
            await self._session_store.ensure_restaurant(
                restaurant_id,
                str(bundle.menu.get("name", restaurant_id)),
            )
            cart = await self._session_store.load_cart(restaurant_id, call_id)
            self._sessions[key] = OrderService(catalog, cart=cart)
        return self._sessions[key]

    async def reset_call(self, restaurant_id: str, call_id: str) -> None:
        key = self._session_key(restaurant_id, call_id)
        self._sessions.pop(key, None)
        self._active_order_ids.pop(key, None)
        self._memory_caller_phones.pop(key, None)
        await self._session_store.delete_session(restaurant_id, call_id)

    async def persist_session(
        self, restaurant_id: str, call_id: str, service: OrderService
    ) -> None:
        await self._session_store.save_cart(restaurant_id, call_id, service.cart)
        key = self._session_key(restaurant_id, call_id)
        order_id = self._active_order_ids.get(key)
        if order_id is not None:
            spoken, sms = service.get_summary()
            await self._order_store.update_order(order_id, service.cart, spoken, sms)

    def build_response(
        self,
        service: OrderService,
        result: AddItemResult | OperationResult,
        *,
        order_id: uuid.UUID | None = None,
        sms_sent: bool | None = None,
        payment_required: bool | None = None,
    ) -> ToolResponse:
        spoken, sms = service.get_summary()
        return ToolResponse(
            status=result.status.value,
            message=result.message,
            line_id=getattr(result, "line_id", None),
            options=getattr(result, "options", []) or [],
            cart=service.cart.model_dump(),
            spoken_summary=spoken,
            sms_summary=sms,
            order_id=str(order_id) if order_id else None,
            sms_sent=sms_sent,
            payment_required=payment_required,
        )

    async def add_item(
        self,
        restaurant_id: str,
        call_id: str,
        *,
        item_term: str = "",
        item_id: str | None = None,
        requested_modifiers: list[str] | None = None,
        quantity: int = 1,
        special_instructions: str = "",
    ) -> ToolResponse:
        service = await self.get_service(restaurant_id, call_id)
        closed = self._ensure_store_open(restaurant_id, service)
        if closed is not None:
            return closed
        if item_id:
            result = service.add_item_by_id(
                item_id,
                requested_modifiers=requested_modifiers,
                quantity=quantity,
                special_instructions=special_instructions,
            )
        else:
            result = service.add_item(
                item_term,
                requested_modifiers=requested_modifiers,
                quantity=quantity,
                special_instructions=special_instructions,
            )
        await self.persist_session(restaurant_id, call_id, service)
        key = self._session_key(restaurant_id, call_id)
        return self.build_response(service, result, order_id=self._active_order_ids.get(key))

    async def remove_item(self, restaurant_id: str, call_id: str, line_id: str) -> ToolResponse:
        service = await self.get_service(restaurant_id, call_id)
        result = service.remove_item(line_id)
        await self.persist_session(restaurant_id, call_id, service)
        key = self._session_key(restaurant_id, call_id)
        return self.build_response(service, result, order_id=self._active_order_ids.get(key))

    async def set_modifiers(
        self,
        restaurant_id: str,
        call_id: str,
        line_id: str,
        requested_modifiers: list[str],
    ) -> ToolResponse:
        service = await self.get_service(restaurant_id, call_id)
        result = service.set_modifiers(line_id, requested_modifiers)
        await self.persist_session(restaurant_id, call_id, service)
        key = self._session_key(restaurant_id, call_id)
        return self.build_response(service, result, order_id=self._active_order_ids.get(key))

    async def get_cart(self, restaurant_id: str, call_id: str) -> ToolResponse:
        service = await self.get_service(restaurant_id, call_id)
        result = service.get_cart()
        key = self._session_key(restaurant_id, call_id)
        return self.build_response(service, result, order_id=self._active_order_ids.get(key))

    async def check_ambiguity(self, restaurant_id: str, call_id: str, query: str) -> ToolResponse:
        service = await self.get_service(restaurant_id, call_id)
        result = service.check_ambiguity(query)
        key = self._session_key(restaurant_id, call_id)
        return self.build_response(service, result, order_id=self._active_order_ids.get(key))

    async def checkout(
        self,
        restaurant_id: str,
        call_id: str,
        customer_phone: str = "",
    ) -> ToolResponse:
        service = await self.get_service(restaurant_id, call_id)
        closed = self._ensure_store_open(restaurant_id, service)
        if closed is not None:
            return closed
        if not service.cart.lines:
            result = OperationResult(
                status=OrderResultStatus.VIOLATION,
                message="Cannot checkout with an empty cart.",
                cart=service.cart,
            )
            return self.build_response(service, result)

        if customer_phone:
            service.cart.customer_phone = normalize_phone(customer_phone)

        spoken, sms = service.get_summary()
        phone = await self._resolve_customer_phone(restaurant_id, call_id, customer_phone)
        if phone and not service.cart.customer_phone:
            service.cart.customer_phone = phone
        elif not phone:
            phone = service.cart.customer_phone

        parity = check_order_parity(
            spoken_summary=spoken,
            sms_summary=sms,
            total_cents=service.cart.total_cents,
        )
        if not parity.ok:
            raise HTTPException(
                status_code=500,
                detail=f"Checkout parity check failed: {'; '.join(parity.errors)}",
            )

        record = await self._order_store.create_order(
            restaurant_id=restaurant_id,
            call_id=call_id,
            cart=service.cart,
            spoken_summary=spoken,
            sms_summary=sms,
            customer_phone=phone,
            status="open",
        )
        if record is None:
            order_id = uuid.uuid4()
            record = OrderRecord(
                id=order_id,
                restaurant_id=restaurant_id,
                call_id=call_id,
                customer_phone=phone,
                status="open",
                cart=service.cart,
                spoken_summary=spoken,
                sms_summary=sms,
                created_at=datetime.now(UTC),
            )
            self._memory_orders[order_id] = record

        key = self._session_key(restaurant_id, call_id)
        self._active_order_ids[key] = record.id
        await self.persist_session(restaurant_id, call_id, service)

        sms_sent = False
        settings = get_settings()
        if phone and sms:
            sms_result = await send_order_sms(
                settings.sms_gateway_url,
                SendSmsRequest(
                    order_id=str(record.id),
                    to_phone=phone,
                    body=sms,
                    restaurant_id=restaurant_id,
                ),
            )
            sms_sent = sms_result.status == "sent"
            if sms_sent and sms_result.sms_id:
                await self._sms_store.save_message(
                    order_id=record.id,
                    sms_id=sms_result.sms_id,
                    restaurant_id=restaurant_id,
                    to_phone=phone,
                    body=sms,
                    status=sms_result.status,
                )

        result = OperationResult(
            status=OrderResultStatus.SUCCESS,
            message=f"Order confirmed. Your order ID is {record.id}.",
            cart=service.cart,
        )
        return self.build_response(
            service,
            result,
            order_id=record.id,
            sms_sent=sms_sent,
            payment_required=True,
        )

    async def capture_payment(
        self,
        restaurant_id: str,
        order_id: str,
        *,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvv: str,
        call_id: str = "",
    ) -> PaymentCaptureResponse:
        try:
            oid = uuid.UUID(order_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid order ID.") from exc

        record = await self._get_order_record(oid)
        if record is None or record.restaurant_id != restaurant_id:
            raise HTTPException(status_code=404, detail="Order not found.")

        amount = record.cart.total_cents
        settings = get_settings()
        charge = await charge_payment(
            settings.payment_service_url,
            ChargeRequest(
                order_id=str(record.id),
                amount_cents=amount,
                card_number=card_number,
                exp_month=exp_month,
                exp_year=exp_year,
                cvv=cvv,
                call_id=call_id,
            ),
        )
        if charge.status == "succeeded":
            parity = check_order_parity(
                spoken_summary=record.spoken_summary or "",
                sms_summary=record.sms_summary or "",
                total_cents=amount,
                payment_cents=amount,
            )
            if not parity.ok:
                raise HTTPException(
                    status_code=500,
                    detail=f"Payment parity check failed: {'; '.join(parity.errors)}",
                )
            await self._order_store.update_status(oid, "paid")
            if charge.charge_id:
                await self._payment_store.save_charge(
                    order_id=oid,
                    charge_id=charge.charge_id,
                    amount_cents=amount,
                    last_four=charge.last_four,
                    token=charge.token,
                    status=charge.status,
                    call_id=call_id,
                )
            if oid in self._memory_orders:
                mem = self._memory_orders[oid]
                self._memory_orders[oid] = OrderRecord(
                    id=mem.id,
                    restaurant_id=mem.restaurant_id,
                    call_id=mem.call_id,
                    customer_phone=mem.customer_phone,
                    status="paid",
                    cart=mem.cart,
                    spoken_summary=mem.spoken_summary,
                    sms_summary=mem.sms_summary,
                    created_at=mem.created_at,
                )
        return PaymentCaptureResponse(
            status=charge.status,
            message=charge.message,
            order_id=str(record.id),
            amount_cents=amount,
            last_four=charge.last_four,
            charge_id=charge.charge_id,
        )

    async def resume_order_by_phone(
        self,
        restaurant_id: str,
        call_id: str,
        customer_phone: str,
    ) -> ToolResponse:
        record = await self._order_store.find_latest_open_by_phone(restaurant_id, customer_phone)
        if record is None:
            service = await self.get_service(restaurant_id, call_id)
            result = OperationResult(
                status=OrderResultStatus.NOT_FOUND,
                message=f"No open order found for phone {customer_phone}.",
                cart=service.cart,
            )
            return self.build_response(service, result)

        key = self._session_key(restaurant_id, call_id)
        catalog = MenuCatalog.from_path(self._config_dir(restaurant_id))
        service = OrderService(catalog, cart=record.cart)
        self._sessions[key] = service
        self._active_order_ids[key] = record.id
        await self.persist_session(restaurant_id, call_id, service)
        result = OperationResult(
            status=OrderResultStatus.SUCCESS,
            message=f"Resumed open order {record.id}.",
            cart=service.cart,
        )
        return self.build_response(service, result, order_id=record.id)

    def escalate_call(self, restaurant_id: str, call_id: str, reason: str = "") -> dict:
        """Sprint 5.6 — return staff transfer target for human escalation."""
        status = self.store_status(restaurant_id)
        phone = status.get("escalation_phone")
        if not phone:
            raise HTTPException(
                status_code=404,
                detail="No escalation phone configured for this restaurant.",
            )
        why = reason.strip() or "customer_requested"
        return {
            "status": "escalating",
            "call_id": call_id,
            "reason": why,
            "transfer_to": phone,
            "message": "Please hold while I connect you with a team member.",
        }

    def _record_in_day(self, record: OrderRecord, day: str, timezone_name: str) -> bool:
        if record.created_at is None:
            return day == "all"
        start, end = _day_bounds_utc(day, timezone_name)
        created = record.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return start <= created < end

    async def list_orders(
        self,
        restaurant_id: str,
        *,
        day: str = "today",
        limit: int = 100,
    ) -> tuple[list[OrderListItem], str]:
        bundle = self.get_bundle(restaurant_id)
        tz = str(bundle.operations.get("timezone", "America/New_York"))
        records = await self._order_store.list_orders(
            restaurant_id, day=day, limit=limit, timezone_name=tz
        )
        seen = {r.id for r in records}
        for mem in self._memory_orders.values():
            if mem.restaurant_id != restaurant_id or mem.id in seen:
                continue
            if self._record_in_day(mem, day, tz):
                records.append(mem)
        records.sort(key=lambda r: r.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        records = records[:limit]
        items = [self._to_list_item(r) for r in records]
        return items, tz

    def _to_list_item(self, record: OrderRecord) -> OrderListItem:
        lines = record.cart.lines
        preview = None
        if record.spoken_summary:
            preview = record.spoken_summary.strip().split("\n")[0][:120]
        created = record.created_at.isoformat() if record.created_at else None
        return OrderListItem(
            order_id=str(record.id),
            call_id=record.call_id,
            customer_phone=record.customer_phone,
            status=record.status,
            total_cents=record.cart.total_cents,
            item_count=len(lines),
            created_at=created,
            summary_preview=preview,
        )

    async def invoke_tool(
        self,
        restaurant_id: str,
        call_id: str,
        tool: str,
        arguments: dict,
    ) -> ToolResponse:
        name = tool.strip().lower()
        if name == "add_item":
            return await self.add_item(
                restaurant_id,
                call_id,
                item_term=str(arguments.get("item_term", "")),
                item_id=arguments.get("item_id"),
                requested_modifiers=list(arguments.get("requested_modifiers") or []),
                quantity=int(arguments.get("quantity") or 1),
                special_instructions=str(arguments.get("special_instructions") or ""),
            )
        if name == "remove_item":
            return await self.remove_item(restaurant_id, call_id, str(arguments.get("line_id", "")))
        if name == "set_modifier":
            return await self.set_modifiers(
                restaurant_id,
                call_id,
                str(arguments.get("line_id", "")),
                list(arguments.get("requested_modifiers") or []),
            )
        if name == "get_cart":
            return await self.get_cart(restaurant_id, call_id)
        if name == "check_ambiguity":
            return await self.check_ambiguity(
                restaurant_id, call_id, str(arguments.get("query", ""))
            )
        if name == "checkout":
            return await self.checkout(
                restaurant_id, call_id, str(arguments.get("customer_phone") or "")
            )
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool}")


use_cases = CallOrderUseCases()
