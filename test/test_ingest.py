import pytest
import uuid
import base64
from datetime import datetime, timezone


# Вспомогательные функции для создания тестовых данных
def make_event(seq: int, type: str, data: dict = None, state: str = None) -> dict:
    """Создаёт тестовое событие."""
    return {
        "seq": seq,
        "ts": "2026-05-29T10:00:00Z",
        "t_offset_ms": seq * 1000,
        "type": type,
        "state": state,
        "data": data or {},
    }


def make_batch(session_id: str, events: list[dict], batch_id: str = None) -> dict:
    """Создаёт тестовый батч."""
    return {
        "bot_id": "test-bot",
        "session_id": session_id,
        "batch_id": batch_id or str(uuid.uuid4()),
        "events": events,
    }


def make_basic_auth_header(username: str, password: str) -> dict:
    """Создаёт заголовок Basic Auth."""
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


class TestHealthCheck:
    """Тесты health check эндпоинта."""

    @pytest.mark.anyio
    async def test_health_check(self, client):
        """GET /api/v1/health возвращает 200 и status ok."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestIngestAuth:
    """Тесты аутентификации ingest эндпоинта."""

    @pytest.mark.anyio
    async def test_ingest_requires_token(self, client):
        """POST /api/v1/events без X-Bot-Token возвращает 401."""
        batch = make_batch(
            "test-session-1",
            [make_event(0, "session_start", {"channelType": "telegram"})]
        )
        response = await client.post("/api/v1/events", json=batch)
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_ingest_wrong_token(self, client):
        """POST /api/v1/events с неправильным X-Bot-Token возвращает 401."""
        batch = make_batch(
            "test-session-1",
            [make_event(0, "session_start", {"channelType": "telegram"})]
        )
        response = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": "wrong-token"}
        )
        assert response.status_code == 401


class TestIngestSessionCreation:
    """Тесты создания сессии при ingest."""

    @pytest.mark.anyio
    async def test_ingest_creates_session(self, client):
        """POST создаёт сессию из session_start события."""
        from test.conftest import TEST_TOKEN, TEST_USER, TEST_PASSWORD

        session_id = "session-" + str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        # Отправляем батч с session_start
        batch = make_batch(
            session_id,
            [
                make_event(
                    0,
                    "session_start",
                    {
                        "channelType": "telegram",
                        "userId": "user-123",
                        "userFrom": "user123",
                        "entryQuery": "привет",
                    },
                )
            ],
            batch_id=batch_id,
        )

        response = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["accepted"] == 1
        assert data["deduped"] == 0

        # Проверяем что сессия создалась через GET /api/v1/sessions/{session_id}
        auth_header = make_basic_auth_header(TEST_USER, TEST_PASSWORD)
        get_response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header,
        )
        assert get_response.status_code == 200
        session_data = get_response.json()

        session = session_data["session"]
        assert session["id"] == session_id
        assert session["bot_id"] == "test-bot"
        assert session["channel_type"] == "telegram"
        assert session["user_id"] == "user-123"
        assert session["user_from"] == "user123"
        assert session["entry_query"] == "привет"
        assert session["status"] == "active"
        assert session["events_count"] == 1


class TestIngestDedup:
    """Тесты дедупликации батчей и событий."""

    @pytest.mark.anyio
    async def test_batch_dedup(self, client):
        """Второй запрос с одинаковым batch_id возвращает deduped count."""
        from test.conftest import TEST_TOKEN

        session_id = "session-" + str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        batch = make_batch(
            session_id,
            [
                make_event(0, "session_start"),
                make_event(1, "message", {"text": "hello"}),
                make_event(2, "message", {"text": "world"}),
            ],
            batch_id=batch_id,
        )

        # Первый запрос
        response1 = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response1.status_code == 200
        assert response1.json()["accepted"] == 3
        assert response1.json()["deduped"] == 0

        # Второй запрос с тем же batch_id
        response2 = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response2.status_code == 200
        assert response2.json()["accepted"] == 0
        assert response2.json()["deduped"] == 3

    @pytest.mark.anyio
    async def test_event_dedup(self, client):
        """События с одинаковым seq пропускаются."""
        from test.conftest import TEST_TOKEN

        session_id = "session-" + str(uuid.uuid4())

        # Первый батч: seq=[0, 1, 2]
        batch1 = make_batch(
            session_id,
            [
                make_event(0, "session_start"),
                make_event(1, "message", {"text": "msg1"}),
                make_event(2, "message", {"text": "msg2"}),
            ],
            batch_id=str(uuid.uuid4()),
        )

        response1 = await client.post(
            "/api/v1/events",
            json=batch1,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response1.status_code == 200
        assert response1.json()["accepted"] == 3

        # Второй батч: seq=[2, 3, 4] (пересечение на seq=2)
        batch2 = make_batch(
            session_id,
            [
                make_event(2, "message", {"text": "msg2"}),  # деуплицируется
                make_event(3, "message", {"text": "msg3"}),
                make_event(4, "message", {"text": "msg4"}),
            ],
            batch_id=str(uuid.uuid4()),
        )

        response2 = await client.post(
            "/api/v1/events",
            json=batch2,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response2.status_code == 200
        assert response2.json()["accepted"] == 2
        assert response2.json()["deduped"] == 1


class TestIngestSessionEnd:
    """Тесты обновления статуса сессии при завершении."""

    @pytest.mark.anyio
    async def test_session_end_updates_status(self, client):
        """Событие session_end обновляет status и duration_ms."""
        from test.conftest import TEST_TOKEN, TEST_USER, TEST_PASSWORD

        session_id = "session-" + str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        batch = make_batch(
            session_id,
            [
                make_event(0, "session_start"),
                make_event(1, "session_end", {"reason": "end", "duration_ms": 5000}),
            ],
            batch_id=batch_id,
        )

        response = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response.status_code == 200
        assert response.json()["accepted"] == 2

        # Проверяем статус сессии
        auth_header = make_basic_auth_header(TEST_USER, TEST_PASSWORD)
        get_response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header,
        )
        assert get_response.status_code == 200
        session = get_response.json()["session"]

        assert session["status"] == "ended"
        assert session["duration_ms"] == 5000
        assert session["ended_at"] is not None


class TestIngestErrorFlag:
    """Тесты установки флага ошибки."""

    @pytest.mark.anyio
    async def test_error_flag(self, client):
        """Событие типа error устанавливает has_error флаг."""
        from test.conftest import TEST_TOKEN, TEST_USER, TEST_PASSWORD

        session_id = "session-" + str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        batch = make_batch(
            session_id,
            [
                make_event(0, "session_start"),
                make_event(1, "error", {"error_code": "ERR_TIMEOUT"}),
            ],
            batch_id=batch_id,
        )

        response = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response.status_code == 200

        # Проверяем флаг has_error
        auth_header = make_basic_auth_header(TEST_USER, TEST_PASSWORD)
        get_response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header,
        )
        assert get_response.status_code == 200
        session = get_response.json()["session"]
        assert session["has_error"] is True


class TestIngestOperatorTransfer:
    """Тесты установки флага передачи оператору."""

    @pytest.mark.anyio
    async def test_operator_transfer_flag(self, client):
        """Событие типа operator_transfer устанавливает transferred_to_operator флаг."""
        from test.conftest import TEST_TOKEN, TEST_USER, TEST_PASSWORD

        session_id = "session-" + str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        batch = make_batch(
            session_id,
            [
                make_event(0, "session_start"),
                make_event(1, "operator_transfer", {"operator_id": "op-123"}),
            ],
            batch_id=batch_id,
        )

        response = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response.status_code == 200

        # Проверяем флаг transferred_to_operator
        auth_header = make_basic_auth_header(TEST_USER, TEST_PASSWORD)
        get_response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header,
        )
        assert get_response.status_code == 200
        session = get_response.json()["session"]
        assert session["transferred_to_operator"] is True


class TestIngestEventsCount:
    """Тесты накопления счётчика событий."""

    @pytest.mark.anyio
    async def test_events_count_accumulates(self, client):
        """Счётчик events_count накапливается при добавлении новых событий."""
        from test.conftest import TEST_TOKEN, TEST_USER, TEST_PASSWORD

        session_id = "session-" + str(uuid.uuid4())

        # Первый батч: 2 события
        batch1 = make_batch(
            session_id,
            [
                make_event(0, "session_start"),
                make_event(1, "message", {"text": "hello"}),
            ],
            batch_id=str(uuid.uuid4()),
        )

        response1 = await client.post(
            "/api/v1/events",
            json=batch1,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response1.status_code == 200
        assert response1.json()["accepted"] == 2

        # Второй батч: 3 события (не пересекаются по seq)
        batch2 = make_batch(
            session_id,
            [
                make_event(2, "message", {"text": "world"}),
                make_event(3, "message", {"text": "foo"}),
                make_event(4, "message", {"text": "bar"}),
            ],
            batch_id=str(uuid.uuid4()),
        )

        response2 = await client.post(
            "/api/v1/events",
            json=batch2,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response2.status_code == 200
        assert response2.json()["accepted"] == 3

        # Проверяем что events_count = 5
        auth_header = make_basic_auth_header(TEST_USER, TEST_PASSWORD)
        get_response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header,
        )
        assert get_response.status_code == 200
        session = get_response.json()["session"]
        assert session["events_count"] == 5


class TestIngestLastState:
    """Тесты обновления last_state и последнего события."""

    @pytest.mark.anyio
    async def test_last_state_updated(self, client):
        """Поле last_state обновляется на последнее событие."""
        from test.conftest import TEST_TOKEN, TEST_USER, TEST_PASSWORD

        session_id = "session-" + str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        batch = make_batch(
            session_id,
            [
                make_event(0, "session_start", state="Main"),
                make_event(1, "message", state="Inquiry"),
                make_event(2, "message", state="Confirm"),
            ],
            batch_id=batch_id,
        )

        response = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response.status_code == 200

        # Проверяем last_state
        auth_header = make_basic_auth_header(TEST_USER, TEST_PASSWORD)
        get_response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header,
        )
        assert get_response.status_code == 200
        session = get_response.json()["session"]
        assert session["last_state"] == "Confirm"


class TestIngestEvents:
    """Тесты доступа к событиям через GET сессии."""

    @pytest.mark.anyio
    async def test_events_retrieved(self, client):
        """События доступны через GET /api/v1/sessions/{session_id}."""
        from test.conftest import TEST_TOKEN, TEST_USER, TEST_PASSWORD

        session_id = "session-" + str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        batch = make_batch(
            session_id,
            [
                make_event(0, "session_start", {"test": "data"}),
                make_event(1, "message", {"text": "hello"}),
            ],
            batch_id=batch_id,
        )

        response = await client.post(
            "/api/v1/events",
            json=batch,
            headers={"X-Bot-Token": TEST_TOKEN},
        )
        assert response.status_code == 200

        # Получаем события через GET
        auth_header = make_basic_auth_header(TEST_USER, TEST_PASSWORD)
        get_response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header,
        )
        assert get_response.status_code == 200
        data = get_response.json()

        assert len(data["events"]) == 2
        assert data["events"][0]["seq"] == 0
        assert data["events"][0]["type"] == "session_start"
        assert data["events"][0]["data"]["test"] == "data"
        assert data["events"][1]["seq"] == 1
        assert data["events"][1]["type"] == "message"
        assert data["events"][1]["data"]["text"] == "hello"
