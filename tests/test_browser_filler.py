import os
import tempfile
from playwright.sync_api import sync_playwright

from user_forge.core.models import Account
from user_forge.modules.browser_bot.form_filler import FormFiller
from user_forge.modules.browser_bot.session_saver import SessionSaver

MOCK_SIGNUP_HTML = """
<!DOCTYPE html>
<html>
<head><title>Mock Signup Form</title></head>
<body>
    <form id="signup-form">
        <input type="text" name="firstname" placeholder="Nombre" />
        <input type="text" name="lastname" placeholder="Apellido" />
        <input type="text" name="username" placeholder="Usuario" />
        <input type="email" name="email" placeholder="Correo electrónico" />
        <input type="password" name="password" placeholder="Contraseña" />
        <input type="password" name="confirm_password" placeholder="Repetir contraseña" />
        <input type="checkbox" name="terms" />
        <button type="submit" id="btn-submit">Registrarse</button>
    </form>
</body>
</html>
"""

def test_form_filler_heuristics_and_session_save():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mock_file = os.path.join(tmp_dir, "signup.html")
        with open(mock_file, "w", encoding="utf-8") as f:
            f.write(MOCK_SIGNUP_HTML)

        account = Account(
            id=1,
            project_id="test",
            username="lucas_test",
            email="lucas@test.com",
            password_encrypted="dummy",
            full_name="Lucas Gomez"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            page.goto(f"file:///{mock_file.replace(os.sep, '/')}")

            filler = FormFiller(page)
            report = filler.fill_signup_form(account, "SecureP@ssw0rd123!")

            # Verify that fields were detected and filled
            assert report["email_filled"] is True
            assert report["username_filled"] is True
            assert report["password_filled"] is True
            assert report["confirm_password_filled"] is True
            assert report["firstname_filled"] is True
            assert report["lastname_filled"] is True
            assert report["terms_checked"] is True

            # Verify DOM element values
            assert page.locator("input[name='email']").input_value() == "lucas@test.com"
            assert page.locator("input[name='username']").input_value() == "lucas_test"
            assert page.locator("input[name='firstname']").input_value() == "Lucas"
            assert page.locator("input[name='lastname']").input_value() == "Gomez"
            assert page.locator("input[name='terms']").is_checked() is True

            # Test SessionSaver
            saver = SessionSaver()
            from pathlib import Path
            saver.save_session_state(context, Path(tmp_dir))
            summary = saver.get_state_summary(Path(tmp_dir))
            assert summary["exists"] is True

            context.close()
            browser.close()
