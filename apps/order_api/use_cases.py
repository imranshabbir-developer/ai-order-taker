from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException
from order_engine.catalog import MenuCatalog
from order_engine.config_loader import RestaurantConfigBundle
from order_engine.models import OrderResultStatus
from order_engine.order_service import OrderService
from order_engine.results import AddItemResult, OperationResult

from apps.order_api.db.order_store import OrderStore, normalize_phone
from apps.order_api.db.session_store import SessionStore
from apps.order_api.schemas import ToolResponse


class CallOrderUseCases:
    """Application layer — orchestrates domain service, sessions, and orders."""

    def __init__(self) -> None:
        self._sessions: dict[str, OrderService] = {}
        self._config_cache: dict[str, RestaurantConfigBundle] = {}
        self._session_store = SessionStore()
        self._order_store = OrderStore()
        self._active_order_ids: dict[str, uuid.UUID] = {}

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
        phone = normalize_phone(customer_phone) if customer_phone else service.cart.customer_phone
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
            result = OperationResult(
                status=OrderResultStatus.SUCCESS,
                message="Order confirmed (database persistence disabled).",
                cart=service.cart,
            )
            return self.build_response(service, result)

        key = self._session_key(restaurant_id, call_id)
        self._active_order_ids[key] = record.id
        await self.persist_session(restaurant_id, call_id, service)
        result = OperationResult(
            status=OrderResultStatus.SUCCESS,
            message=f"Order confirmed. Your order ID is {record.id}.",
            cart=service.cart,
        )
        return self.build_response(service, result, order_id=record.id)

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
