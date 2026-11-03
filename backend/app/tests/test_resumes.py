import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TargetRole
from app.tests.fakes import an_industry


async def signup(client: AsyncClient, email: str = "owner@example.com") -> dict[str, str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": "Owner"}
    )
    assert response.status_code == 201, response.text
    client.cookies.clear()  # each test user authenticates with their bearer token only
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def role(db_session: AsyncSession) -> TargetRole:
    role = TargetRole(
        name="Full Stack Developer",
        slug="full-stack-developer",
        description="",
        seniority="junior",
        industry=an_industry(),
    )
    db_session.add(role)
    await db_session.commit()
    return role


async def create(client: AsyncClient, headers: dict[str, str], **body: object) -> dict:
    response = await client.post(
        "/api/resumes", json={"title": "My resume", **body}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- create / read ----------------------------------------------------------


async def test_create_prefills_personal_info_from_user(
    client: AsyncClient, role: TargetRole
) -> None:
    headers = await signup(client)

    resume = await create(client, headers, type="cv", target_role_id=str(role.id))

    assert resume["type"] == "cv"
    assert resume["template"] == "classic"
    assert resume["target_role"]["name"] == "Full Stack Developer"
    assert resume["data"]["personal_info"]["full_name"] == "Owner"
    assert resume["data"]["personal_info"]["email"] == "owner@example.com"
    assert resume["data"]["experience"] == []


async def test_create_rejects_unknown_target_role(client: AsyncClient) -> None:
    headers = await signup(client)

    response = await client.post(
        "/api/resumes", json={"title": "x", "target_role_id": str(uuid.uuid4())}, headers=headers
    )

    assert response.status_code == 422


async def test_create_rejects_invalid_data(client: AsyncClient) -> None:
    headers = await signup(client)

    response = await client.post(
        "/api/resumes",
        json={"title": "x", "data": {"experience": [{"company": "Acme"}]}},  # title missing
        headers=headers,
    )

    assert response.status_code == 422


async def test_list_returns_own_resumes_newest_first(client: AsyncClient) -> None:
    headers = await signup(client)
    await create(client, headers, title="First")
    await create(client, headers, title="Second")

    response = await client.get("/api/resumes", headers=headers)

    assert response.status_code == 200
    assert [r["title"] for r in response.json()] == ["Second", "First"]
    assert "data" not in response.json()[0]


async def test_endpoints_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/resumes")).status_code == 401
    assert (await client.get("/api/target-roles")).status_code == 401


# --- ownership --------------------------------------------------------------


async def test_other_users_cannot_see_or_change_a_resume(client: AsyncClient) -> None:
    owner = await signup(client, "owner@example.com")
    intruder = await signup(client, "intruder@example.com")
    resume_id = (await create(client, owner))["id"]
    url = f"/api/resumes/{resume_id}"

    assert (await client.get(url, headers=intruder)).status_code == 404
    assert (await client.patch(url, json={"title": "pwned"}, headers=intruder)).status_code == 404
    assert (await client.post(f"{url}/duplicate", headers=intruder)).status_code == 404
    assert (await client.delete(url, headers=intruder)).status_code == 404
    assert (await client.get("/api/resumes", headers=intruder)).json() == []
    assert (await client.get(url, headers=owner)).json()["title"] == "My resume"


# --- patch ------------------------------------------------------------------


async def test_patch_changes_only_sent_fields(client: AsyncClient, role: TargetRole) -> None:
    headers = await signup(client)
    resume = await create(client, headers, type="cv", target_role_id=str(role.id))

    response = await client.patch(
        f"/api/resumes/{resume['id']}", json={"title": "Renamed"}, headers=headers
    )

    body = response.json()
    assert response.status_code == 200
    assert body["title"] == "Renamed"
    assert body["type"] == "cv"
    assert body["target_role"]["id"] == str(role.id)
    assert body["updated_at"] > resume["updated_at"]


async def test_patch_replaces_data_and_is_idempotent(client: AsyncClient) -> None:
    headers = await signup(client)
    resume = await create(client, headers)
    data = {
        "summary": "Backend developer",
        "experience": [{"company": "Acme", "title": "Engineer", "bullets": ["Built APIs"]}],
    }
    url = f"/api/resumes/{resume['id']}"

    first = await client.patch(url, json={"data": data}, headers=headers)
    second = await client.patch(url, json={"data": data}, headers=headers)

    assert first.status_code == second.status_code == 200
    assert second.json()["data"] == first.json()["data"]
    assert second.json()["data"]["experience"][0]["company"] == "Acme"
    # Whole-document replace: prefilled personal info not in the payload is reset.
    assert second.json()["data"]["personal_info"]["full_name"] == ""


async def test_patch_rejects_invalid_data_without_saving(client: AsyncClient) -> None:
    headers = await signup(client)
    resume = await create(client, headers)
    url = f"/api/resumes/{resume['id']}"

    response = await client.patch(
        url, json={"data": {"personal_info": {"email": "not-an-email"}}}, headers=headers
    )

    assert response.status_code == 422
    stored = (await client.get(url, headers=headers)).json()
    assert stored["data"]["personal_info"]["email"] == "owner@example.com"


async def test_patch_can_clear_target_role(client: AsyncClient, role: TargetRole) -> None:
    headers = await signup(client)
    resume = await create(client, headers, target_role_id=str(role.id))

    response = await client.patch(
        f"/api/resumes/{resume['id']}", json={"target_role_id": None}, headers=headers
    )

    assert response.json()["target_role"] is None


@pytest.mark.parametrize(
    "body", [{"title": None}, {"data": None}, {"title": "  "}, {"ats_score": 99}]
)
async def test_patch_rejects_bad_fields(client: AsyncClient, body: dict[str, object]) -> None:
    headers = await signup(client)
    resume = await create(client, headers)

    response = await client.patch(f"/api/resumes/{resume['id']}", json=body, headers=headers)

    assert response.status_code == 422


# --- duplicate / delete -----------------------------------------------------


async def test_duplicate_copies_content_with_new_id(client: AsyncClient) -> None:
    headers = await signup(client)
    resume = await create(client, headers, data={"summary": "Original"})

    response = await client.post(f"/api/resumes/{resume['id']}/duplicate", headers=headers)

    copy = response.json()
    assert response.status_code == 201
    assert copy["id"] != resume["id"]
    assert copy["title"] == "My resume (copy)"
    assert copy["data"]["summary"] == "Original"


async def test_delete_removes_resume(client: AsyncClient) -> None:
    headers = await signup(client)
    resume = await create(client, headers)
    url = f"/api/resumes/{resume['id']}"

    assert (await client.delete(url, headers=headers)).status_code == 204
    assert (await client.get(url, headers=headers)).status_code == 404


# --- target roles -----------------------------------------------------------


async def test_list_target_roles(client: AsyncClient, role: TargetRole) -> None:
    headers = await signup(client)

    response = await client.get("/api/target-roles", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "full-stack-developer"
