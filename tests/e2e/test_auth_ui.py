"""Frontend: Login, Register y control de sesión."""
from playwright.sync_api import Page, expect

from conftest import ADMIN_EMAIL, BASE_URL, login


def test_pagina_login_carga(page: Page):
    page.goto("/")
    expect(page).to_have_title("Iniciar sesión | SA")
    expect(page.get_by_test_id("login-form")).to_be_visible()
    expect(page.get_by_test_id("login-submit")).to_have_text("Entrar")


def test_login_correcto_redirige_a_usuarios(page: Page):
    login(page)
    expect(page).to_have_url(f"{BASE_URL}/users.html")
    expect(page.get_by_test_id("current-user")).to_have_text(ADMIN_EMAIL)


def test_login_password_incorrecto_muestra_error(page: Page):
    login(page, password="incorrecta")
    expect(page.get_by_test_id("login-alert")).to_have_text("Credenciales inválidas")
    expect(page).to_have_url(f"{BASE_URL}/index.html")


def test_registro_y_login_del_nuevo_usuario(page: Page, unique_email):
    page.goto("/")
    page.get_by_test_id("go-register").click()
    expect(page).to_have_url(f"{BASE_URL}/register.html")

    page.get_by_test_id("register-name").fill("Usuario E2E")
    page.get_by_test_id("register-email").fill(unique_email)
    page.get_by_test_id("register-password").fill("secreto123")
    page.get_by_test_id("register-confirm").fill("secreto123")
    page.get_by_test_id("register-submit").click()

    expect(page.get_by_test_id("login-alert")).to_contain_text("Cuenta creada")
    login(page, unique_email, "secreto123")
    expect(page.get_by_test_id("current-user")).to_have_text(unique_email)


def test_registro_contrasenas_distintas(page: Page, unique_email):
    page.goto("/register.html")
    page.get_by_test_id("register-name").fill("Usuario E2E")
    page.get_by_test_id("register-email").fill(unique_email)
    page.get_by_test_id("register-password").fill("secreto123")
    page.get_by_test_id("register-confirm").fill("otra-cosa")
    page.get_by_test_id("register-submit").click()
    expect(page.get_by_test_id("register-alert")).to_have_text("Las contraseñas no coinciden")


def test_registro_email_duplicado(page: Page):
    page.goto("/register.html")
    page.get_by_test_id("register-name").fill("Duplicado")
    page.get_by_test_id("register-email").fill(ADMIN_EMAIL)
    page.get_by_test_id("register-password").fill("secreto123")
    page.get_by_test_id("register-confirm").fill("secreto123")
    page.get_by_test_id("register-submit").click()
    expect(page.get_by_test_id("register-alert")).to_have_text("El email ya está registrado")


def test_pagina_protegida_sin_sesion_redirige_a_login(page: Page):
    page.goto("/users.html")
    expect(page).to_have_url(f"{BASE_URL}/index.html")


def test_cerrar_sesion(logged_page: Page):
    logged_page.get_by_test_id("logout").click()
    expect(logged_page).to_have_url(f"{BASE_URL}/index.html")
    logged_page.goto("/users.html")
    expect(logged_page).to_have_url(f"{BASE_URL}/index.html")
