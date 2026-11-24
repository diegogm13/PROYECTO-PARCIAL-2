"""Pruebas E2E con Playwright contra el stack levantado con docker compose (NGINX en :80).

    docker compose up -d --build --wait
    pytest tests/e2e                      # E2E_BASE_URL=http://localhost por defecto
"""
import os
import uuid

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@sa.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")

expect.set_options(timeout=10_000)


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture
def unique_email():
    return f"e2e-{uuid.uuid4().hex[:10]}@test.com"


def login(page: Page, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    page.goto("/index.html")
    page.get_by_test_id("login-email").fill(email)
    page.get_by_test_id("login-password").fill(password)
    page.get_by_test_id("login-submit").click()


@pytest.fixture
def logged_page(page: Page):
    login(page)
    expect(page).to_have_url(f"{BASE_URL}/users.html")
    expect(page.get_by_test_id("users-title")).to_be_visible()
    return page
