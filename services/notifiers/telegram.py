"""Telegram notifier implementation using the Bot API via httpx."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from io import BytesIO

import httpx

from services.telegram_bot import BOT_COMMANDS, TelegramBotHandler
from services.telegram_config import TelegramConfig

from . import BaseNotifier, Notification

_LOGGER = logging.getLogger(__name__)


class TelegramNotifier(BaseNotifier):
    """Sends notifications via Telegram Bot API."""

    def __init__(self, config: TelegramConfig) -> None:
        self._config = config
        self._bot_token = config.bot_token
        self._chat_id = config.chat_id
        self._base_url = config.base_url
        self._callback_handler: asyncio.Task | None = None
        self._callback_listeners: dict[
            str, object
        ] = {}  # callback_data_prefix -> dispatcher ref
        self._last_update_id: int = 0
        self._bot_handler: TelegramBotHandler | None = None

    async def send(self, notification: Notification) -> bool:
        """Send a text message with HTML formatting."""
        text = self._format_message(notification)
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        # Add inline keyboard if provided
        if notification.extra.get("reply_markup"):
            payload["reply_markup"] = notification.extra["reply_markup"]
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self._base_url}/sendMessage", json=payload)
                if resp.status_code == 200:
                    return True
                _LOGGER.warning(
                    "Telegram sendMessage failed: %d %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
        except Exception as exc:
            _LOGGER.error("Telegram send error: %s", exc)
            return False

    async def send_photo(self, notification: Notification) -> bool:
        """Send a photo with caption."""
        if not notification.image:
            return await self.send(notification)

        caption = self._format_message(notification)
        # Telegram caption limit is 1024 chars
        if len(caption) > 1024:
            caption = caption[:1020] + "..."

        files = {
            "photo": ("vehicle.png", BytesIO(notification.image), "image/png"),
        }
        data = {
            "chat_id": self._chat_id,
            "caption": caption,
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/sendPhoto", data=data, files=files
                )
                if resp.status_code == 200:
                    return True
                _LOGGER.warning(
                    "Telegram sendPhoto failed: %d %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
        except Exception as exc:
            _LOGGER.error("Telegram send_photo error: %s", exc)
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Send a test message to verify bot configuration."""
        payload = {
            "chat_id": self._chat_id,
            "text": (
                "✅ <b>LeapConnect</b> — Notifications active!\n\n"
                "Connection configured successfully."
            ),
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self._base_url}/sendMessage", json=payload)
                if resp.status_code == 200:
                    return True, "Test message sent successfully"
                data = (
                    resp.json()
                    if resp.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                description = data.get("description", resp.text[:100])
                return False, f"Telegram error: {description}"
        except httpx.TimeoutException:
            return False, "Connection timeout to Telegram"
        except Exception as exc:
            return False, f"Error: {exc}"

    @staticmethod
    def _format_message(notification: Notification) -> str:
        """Build an HTML-formatted Telegram message."""
        parts = []
        parts.append(f"<b>{notification.title}</b>")
        if notification.body:
            parts.append(notification.body)
        return "\n".join(parts)

    async def send_location(
        self,
        lat: float,
        lon: float,
        caption: str = "",
        reply_markup: dict | None = None,
    ) -> bool:
        """Send a native Telegram location message with optional inline keyboard."""
        payload: dict = {
            "chat_id": self._chat_id,
            "latitude": lat,
            "longitude": lon,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self._base_url}/sendLocation", json=payload)
                if resp.status_code == 200:
                    return True
                _LOGGER.warning(
                    "Telegram sendLocation failed: %d %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
        except Exception as exc:
            _LOGGER.error("Telegram send_location error: %s", exc)
            return False

    async def answer_callback_query(
        self, callback_query_id: str, text: str = ""
    ) -> None:
        """Acknowledge a callback query."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self._base_url}/answerCallbackQuery",
                    json={
                        "callback_query_id": callback_query_id,
                        "text": text,
                    },
                )
        except Exception as exc:
            _LOGGER.debug("answer_callback_query error: %s", exc)

    def start_callback_polling(self, dispatcher) -> None:
        """Start a background task polling for Telegram updates."""
        if self._callback_handler and not self._callback_handler.done():
            return
        self._callback_listeners["stop_tracking:"] = dispatcher
        # Set up bot command handler only if bot is enabled
        if self._config.bot_enabled:
            vehicle_cache = getattr(dispatcher, "_vehicle_cache", None)
            command_executor = getattr(dispatcher, "_command_executor", None)
            rights_checker = getattr(dispatcher, "_rights_checker", None)
            pin_checker = getattr(dispatcher, "_pin_checker", None)
            pin_setter = getattr(dispatcher, "_pin_setter", None)
            self._bot_handler = TelegramBotHandler(
                vehicle_cache=vehicle_cache,
                command_executor=command_executor,
                notification_dispatcher=dispatcher,
                rights_checker=rights_checker,
                pin_checker=pin_checker,
                pin_setter=pin_setter,
            )
        self._callback_handler = asyncio.create_task(self._poll_updates(dispatcher))

    def stop_callback_polling(self) -> None:
        """Stop the callback polling task."""
        if self._callback_handler and not self._callback_handler.done():
            self._callback_handler.cancel()
            self._callback_handler = None

    async def _poll_updates(self, dispatcher) -> None:
        """Long-poll Telegram for all relevant updates (callbacks + bot commands)."""
        _LOGGER.info("Telegram update polling started")
        await self._set_bot_commands()
        try:
            while True:
                try:
                    async with httpx.AsyncClient(timeout=35) as client:
                        params = {
                            "timeout": 30,
                            "allowed_updates": json.dumps(
                                ["callback_query", "message"]
                            ),
                        }
                        if self._last_update_id:
                            params["offset"] = self._last_update_id + 1
                        resp = await client.get(
                            f"{self._base_url}/getUpdates", params=params
                        )
                        if resp.status_code != 200:
                            await asyncio.sleep(5)
                            continue
                        data = resp.json()
                        for update in data.get("result", []):
                            self._last_update_id = update["update_id"]

                            # Handle callback queries (inline buttons)
                            cq = update.get("callback_query")
                            if cq:
                                await self._handle_callback_query(
                                    client, cq, dispatcher
                                )
                                continue

                            # Handle text messages (bot commands)
                            msg = update.get("message")
                            if msg and msg.get("text"):
                                chat_id = str(msg.get("chat", {}).get("id", ""))
                                if chat_id == self._chat_id:
                                    text = msg["text"]
                                    if text.startswith("/"):
                                        await self._handle_bot_command(client, msg)
                                    elif (
                                        self._bot_handler
                                        and self._bot_handler.awaiting_pin
                                    ):
                                        await self._handle_pin_message(client, msg)

                except httpx.TimeoutException:
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    _LOGGER.warning("Update poll error: %s", exc)
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            _LOGGER.info("Telegram update polling stopped")
        except Exception as exc:
            _LOGGER.error("Update polling fatal: %s", exc)

    async def _handle_callback_query(self, client, cq, dispatcher) -> None:
        """Process an inline keyboard callback."""
        cb_data = cq.get("data", "")
        if cb_data.startswith("stop_tracking:"):
            vin = cb_data.split(":", 1)[1]
            stopped = await dispatcher.stop_tracking(vin)
            ack_text = "✅ Tracking stopped" if stopped else "⚠️ Tracking was not active"
            await self.answer_callback_query(cq["id"], ack_text)
            if cq.get("message"):
                with contextlib.suppress(Exception):
                    await client.post(
                        f"{self._base_url}/editMessageReplyMarkup",
                        json={
                            "chat_id": cq["message"]["chat"]["id"],
                            "message_id": cq["message"]["message_id"],
                            "reply_markup": {"inline_keyboard": []},
                        },
                    )
        elif cb_data.startswith("cmd:"):
            command = cb_data.split(":", 1)[1]
            if self._bot_handler:
                response = await self._bot_handler.handle_command(f"/{command}")
                await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": self._chat_id,
                        "text": response,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
            await self.answer_callback_query(cq["id"])
        else:
            await self.answer_callback_query(cq["id"], "⚠️ Unknown action")

    async def _handle_bot_command(self, client, msg) -> None:
        """Process a bot command message."""
        if not self._bot_handler:
            return
        text = msg.get("text", "")
        response = await self._bot_handler.handle_command(text)
        if not response:
            return
        # For /location, send native location pin
        cmd = text.strip().split()[0].split("@")[0].lstrip("/")
        if cmd == "location":
            import re

            match = re.search(r"Lat: ([\d.-]+) · Lon: ([\d.-]+)", response)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                await client.post(
                    f"{self._base_url}/sendLocation",
                    json={
                        "chat_id": self._chat_id,
                        "latitude": lat,
                        "longitude": lon,
                    },
                )
                return
        await client.post(
            f"{self._base_url}/sendMessage",
            json={
                "chat_id": self._chat_id,
                "text": response,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )

    async def _handle_pin_message(self, client, msg) -> None:
        """Process a PIN input message: delete it, set PIN, execute pending command."""
        chat_id = msg["chat"]["id"]
        message_id = msg["message_id"]
        pin_text = msg.get("text", "").strip()

        # Delete the message containing the PIN immediately
        with contextlib.suppress(Exception):
            await client.post(
                f"{self._base_url}/deleteMessage",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                },
            )

        # Process the PIN and execute the pending command
        response = await self._bot_handler.handle_pin_input(pin_text)
        if response:
            await client.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self._chat_id,
                    "text": response,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )

    async def _set_bot_commands(self) -> None:
        """Register or clear bot commands with Telegram (shows in menu)."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if self._config.bot_enabled:
                    await client.post(
                        f"{self._base_url}/setMyCommands",
                        json={
                            "commands": BOT_COMMANDS,
                        },
                    )
                    _LOGGER.info("Telegram bot commands menu registered")
                else:
                    await client.post(f"{self._base_url}/deleteMyCommands")
                    _LOGGER.info("Telegram bot commands menu cleared (bot disabled)")
        except Exception as exc:
            _LOGGER.debug("Failed to set bot commands: %s", exc)
