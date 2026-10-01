from datetime import date, timedelta

from fastapi.testclient import TestClient

VALID_PURCHASE = {
    "metal": "gold",
    "weight": "100",
    "unit": "g",
    "purchase_date": "2026-09-15",
    "price_paid": "14250.75",
    "currency": "CAD",
}


def post_purchase(client: TestClient, **changes):
    return client.post("/purchases", json={**VALID_PURCHASE, **changes})


def test_create_purchase_returns_saved_purchase(client: TestClient):
    response = post_purchase(client)

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "metal": "gold",
        "weight_oz": "3.21507466",
        "original_weight": "100",
        "original_unit": "g",
        "purchase_date": "2026-09-15",
        "price_paid": "14250.75",
        "currency": "CAD",
    }


def test_create_purchase_in_kilograms(client: TestClient):
    response = post_purchase(client, metal="silver", weight="1", unit="kg")

    assert response.status_code == 201
    assert response.json()["weight_oz"] == "32.15074657"
    assert response.json()["original_unit"] == "kg"


def test_weights_and_prices_accept_json_numbers(client: TestClient):
    response = post_purchase(client, weight=2.5, unit="troy_oz", price_paid=6400.1)

    assert response.status_code == 201
    assert response.json()["weight_oz"] == "2.50000000"
    assert response.json()["price_paid"] == "6400.10"


def test_list_purchases_is_empty_at_first(client: TestClient):
    response = client.get("/purchases")

    assert response.status_code == 200
    assert response.json() == []


def test_list_purchases_newest_first(client: TestClient):
    post_purchase(client, purchase_date="2025-01-10")
    post_purchase(client, purchase_date="2026-03-05")
    post_purchase(client, purchase_date="2025-07-20")

    dates = [p["purchase_date"] for p in client.get("/purchases").json()]

    assert dates == ["2026-03-05", "2025-07-20", "2025-01-10"]


def test_today_is_an_allowed_purchase_date(client: TestClient):
    response = post_purchase(client, purchase_date=date.today().isoformat())

    assert response.status_code == 201


# --- Invalid input is rejected with 422 and nothing is saved ---


def assert_rejected(client: TestClient, response, field: str):
    assert response.status_code == 422
    assert field in [error["loc"][-1] for error in response.json()["detail"]]
    assert client.get("/purchases").json() == []


def test_rejects_zero_weight(client: TestClient):
    assert_rejected(client, post_purchase(client, weight="0"), "weight")


def test_rejects_negative_price(client: TestClient):
    assert_rejected(client, post_purchase(client, price_paid="-5"), "price_paid")


def test_rejects_price_with_more_than_two_decimals(client: TestClient):
    assert_rejected(client, post_purchase(client, price_paid="10.999"), "price_paid")


def test_rejects_unknown_metal(client: TestClient):
    assert_rejected(client, post_purchase(client, metal="copper"), "metal")


def test_rejects_unknown_unit(client: TestClient):
    assert_rejected(client, post_purchase(client, unit="lb"), "unit")


def test_rejects_unknown_currency(client: TestClient):
    assert_rejected(client, post_purchase(client, currency="EUR"), "currency")


def test_rejects_future_purchase_date(client: TestClient):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert_rejected(client, post_purchase(client, purchase_date=tomorrow), "purchase_date")


def test_rejects_missing_field(client: TestClient):
    entry = {**VALID_PURCHASE}
    del entry["metal"]

    assert_rejected(client, client.post("/purchases", json=entry), "metal")


# --- Editing ---


def test_update_purchase_replaces_details_and_recalculates_ounces(client: TestClient):
    purchase_id = post_purchase(client).json()["id"]

    response = client.put(
        f"/purchases/{purchase_id}",
        json={**VALID_PURCHASE, "metal": "silver", "weight": "1", "unit": "kg"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == purchase_id
    assert response.json()["metal"] == "silver"
    assert response.json()["weight_oz"] == "32.15074657"
    assert response.json()["original_weight"] == "1"
    assert response.json()["original_unit"] == "kg"


def test_update_is_saved(client: TestClient):
    purchase_id = post_purchase(client).json()["id"]

    client.put(f"/purchases/{purchase_id}", json={**VALID_PURCHASE, "price_paid": "999.99"})

    [saved] = client.get("/purchases").json()
    assert saved["price_paid"] == "999.99"


def test_update_missing_purchase_returns_404(client: TestClient):
    response = client.put("/purchases/999", json=VALID_PURCHASE)

    assert response.status_code == 404


def test_invalid_update_is_rejected_and_purchase_unchanged(client: TestClient):
    purchase_id = post_purchase(client).json()["id"]

    response = client.put(f"/purchases/{purchase_id}", json={**VALID_PURCHASE, "weight": "0"})

    assert response.status_code == 422
    [saved] = client.get("/purchases").json()
    assert saved["original_weight"] == "100"


# --- Deleting ---


def test_delete_purchase_removes_only_that_purchase(client: TestClient):
    first_id = post_purchase(client, metal="gold").json()["id"]
    second_id = post_purchase(client, metal="silver").json()["id"]

    response = client.delete(f"/purchases/{first_id}")

    assert response.status_code == 204
    assert [p["id"] for p in client.get("/purchases").json()] == [second_id]


def test_delete_missing_purchase_returns_404(client: TestClient):
    response = client.delete("/purchases/999")

    assert response.status_code == 404


def test_deleted_purchase_cannot_be_deleted_again(client: TestClient):
    purchase_id = post_purchase(client).json()["id"]

    client.delete(f"/purchases/{purchase_id}")
    response = client.delete(f"/purchases/{purchase_id}")

    assert response.status_code == 404
