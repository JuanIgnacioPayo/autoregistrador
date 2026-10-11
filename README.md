# UserForge - Modular Identity & Account Provisioning Engine

**UserForge** es una herramienta CLI modular diseñada para resolver el aprovisionamiento masivo de usuarios e identidades tanto en tus propias aplicaciones (APIs, bases de datos) como en plataformas de terceros (mediante navegador asistido con perfiles aislados anti-bloqueo).

---

## 🚀 Arquitectura y Componentes

```text
user_forge/
├── config/
│   └── settings.py          # Configuración central (bóveda, dominios, timeouts)
├── core/
│   ├── vault.py             # Bóveda SQLite cifrada con Fernet (AES-128-CBC)
│   └── models.py            # Modelos Pydantic (Persona, Account, SessionState)
├── modules/
│   ├── personas/            # Generador de identidades con Faker (es_AR) + Email Routing
│   │   ├── generator.py
│   │   └── email_router.py  # Estrategias Plus-addressing (+) y Catch-all
│   ├── seeders/             # Inserción directa en DBs y Auth APIs
│   │   ├── base.py
│   │   ├── sql_seeder.py    # Inserción SQL directa con hashing bcrypt
│   │   └── supabase_seeder.py # Supabase GoTrue Auth (Admin y Público)
│   ├── browser_bot/         # Navegador asistido Playwright
│   │   ├── browser_manager.py # Directorios de perfil aislados por cuenta
│   │   ├── form_filler.py     # Detección heurística y autocompletado
│   │   └── session_saver.py   # Persistencia de cookies y storage_state.json
│   └── export/              # Exportador a JSON, CSV y Bitwarden/1Password
├── cli.py                   # Interfaz de terminal enriquecida con Typer & Rich
└── tests/                   # Suite completa de pruebas con Pytest
```

---

## 🛠️ Comandos CLI Disponibles

### 1. Generación de Personas (`create-persona`)
Crea identidades verosímiles con nombres, bios, contraseñas seguras y aliases de email, guardándolas cifradas en la bóveda:
```bash
python cli.py create-persona --project "salieris" --count 10
```
*Parámetros opcionales:*
* `--role "Community Manager"`: añade una temática o rol a las bios generadas.
* `--domain "midominio.com"`: dominio para los correos.
* `--strategy "plus"` o `"direct"`: formato `alias@dominio.com` o `user+alias@dominio.com`.

---

### 2. Listar Cuentas de la Bóveda (`list-accounts`)
Consulta las cuentas guardadas filtrando por proyecto o estado:
```bash
python cli.py list-accounts --project "salieris"
```

---

### 3. Registro Asistido en Terceros (`signup-assisted`)
Abre un perfil de navegador completamente aislado en `./browser_profiles/<project>/<username>/`, autocompleta el formulario de registro y **pausa la ejecución para resolver CAPTCHAs, SMS o 2FA**:
```bash
python cli.py signup-assisted --account-id 4 --url "https://app.plataforma.com/signup"
```
Una vez resuelto el desafío, presionás **ENTER** en la terminal:
1. Extrae y persiste las cookies y estado de sesión (`storage_state.json`).
2. Marca la cuenta como `ACTIVE` en la bóveda.

---

### 4. Reabrir Sesión Persistente (`open-session`)
Abre directamente el perfil aislado con las cookies y sesiones previamente guardadas (sin tener que volver a iniciar sesión):
```bash
python cli.py open-session --account-id 4
```

---

### 5. Seeder de Bases de Datos Propias (`seed-sql`)
Genera e inserta directamente lotes de usuarios con contraseñas hasheadas en `bcrypt` en tus bases de datos SQLite / SQL:
```bash
python cli.py seed-sql --project "salieris" --db "mi_app.db" --count 20 --table "users"
```

---

### 6. Seeder de Supabase Auth (`seed-supabase`)
Crea usuarios en Supabase Auth mediante la Admin API (confirmando automáticamente el correo electrónico):
```bash
python cli.py seed-supabase --project "salieris" --url "https://xyz.supabase.co" --key "TU_SERVICE_ROLE_KEY" --count 10
```

---

### 7. Exportar Credenciales (`export`)
Exporta las cuentas y contraseñas de un proyecto en formato JSON, CSV o formato compatible con Bitwarden:
```bash
# Formato JSON
python cli.py export --project "salieris" --format json --output accounts.json

# Formato CSV para Bitwarden / 1Password
python cli.py export --project "salieris" --format bitwarden --output bitwarden.csv
```

---

## 🧪 Pruebas Unitarias

Para ejecutar la suite de pruebas automatizadas:
```bash
pytest
```
Todas las pruebas corren sobre entornos simulados y validan la generación, cifrado, seeders y autocompletado heurístico con Playwright.
