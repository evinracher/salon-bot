from app.chat.whatsapp_schemas import (
    extract_inbound_text_messages,
    normalize_customer_phone,
)


def test_normalize_customer_phone_digits() -> None:
    assert normalize_customer_phone("5491122334455") == "+5491122334455"


def test_extract_inbound_text_messages_basic() -> None:
    body = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {"wa_id": "111", "profile": {"name": "N"}},
                            ],
                            "messages": [
                                {
                                    "from": "111",
                                    "id": "m1",
                                    "type": "text",
                                    "text": {"body": "Hi"},
                                },
                            ],
                        },
                    },
                ],
            },
        ],
    }
    msgs = extract_inbound_text_messages(body)
    assert len(msgs) == 1
    assert msgs[0].wa_id == "111"
    assert msgs[0].profile_name == "N"
    assert msgs[0].text == "Hi"
    assert msgs[0].message_id == "m1"


def test_extract_ignores_non_text() -> None:
    body = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "111",
                                    "id": "m2",
                                    "type": "image",
                                    "image": {"id": "x"},
                                },
                            ],
                        },
                    },
                ],
            },
        ],
    }
    assert extract_inbound_text_messages(body) == []
