"""Frontend: CRUD de usuarios desde la interfaz."""
from playwright.sync_api import Page, expect

from conftest import ADMIN_EMAIL


def crear_usuario(page: Page, email, name="Usuario CRUD", role="user"):
    page.get_by_test_id("user-name").fill(name)
    page.get_by_test_id("user-email").fill(email)
    page.get_by_test_id("user-password").fill("secreto123")
    page.get_by_test_id("user-role").select_option(role)
    page.get_by_test_id("user-save").click()


def fila(page: Page, email):
    return page.locator(f'[data-testid=user-row][data-email="{email}"]')


def test_tabla_muestra_al_admin(logged_page: Page):
    expect(fila(logged_page, ADMIN_EMAIL)).to_be_visible()
    expect(fila(logged_page, ADMIN_EMAIL).get_by_test_id("cell-role")).to_have_text("admin")


def test_crear_usuario(logged_page: Page, unique_email):
    crear_usuario(logged_page, unique_email, role="admin")
    expect(logged_page.get_by_test_id("users-alert")).to_have_text("Usuario creado")
    row = fila(logged_page, unique_email)
    expect(row.get_by_test_id("cell-name")).to_have_text("Usuario CRUD")
    expect(row.get_by_test_id("cell-role")).to_have_text("admin")


def test_crear_usuario_email_duplicado(logged_page: Page):
    crear_usuario(logged_page, ADMIN_EMAIL)
    expect(logged_page.get_by_test_id("users-alert")).to_have_text("El email ya está registrado")


def test_editar_usuario(logged_page: Page, unique_email):
    crear_usuario(logged_page, unique_email)
    fila(logged_page, unique_email).get_by_test_id("edit-user").click()
    expect(logged_page.get_by_test_id("form-title")).to_contain_text("Editar usuario")

    logged_page.get_by_test_id("user-name").fill("Nombre Editado")
    logged_page.get_by_test_id("user-active").select_option("false")
    logged_page.get_by_test_id("user-save").click()

    expect(logged_page.get_by_test_id("users-alert")).to_have_text("Usuario actualizado")
    row = fila(logged_page, unique_email)
    expect(row.get_by_test_id("cell-name")).to_have_text("Nombre Editado")
    expect(row.get_by_test_id("cell-active")).to_have_text("Inactivo")


def test_eliminar_usuario(logged_page: Page, unique_email):
    crear_usuario(logged_page, unique_email)
    expect(fila(logged_page, unique_email)).to_be_visible()

    logged_page.once("dialog", lambda dialog: dialog.accept())
    fila(logged_page, unique_email).get_by_test_id("delete-user").click()

    expect(logged_page.get_by_test_id("users-alert")).to_have_text("Usuario eliminado")
    expect(fila(logged_page, unique_email)).to_have_count(0)
