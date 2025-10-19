# Capstone

Proyecto Django para la junta de vecinos (autenticación, roles y panel básico).

## Estructura
- backend / # Proyecto Django
    - junta_ut / # Settings, urls
    - core / # App principal (vista, templates)
- docs / # Material de apoyo (si aplica)


## Requisitos
- Python 3.11+ (recomendado)
- pip
- (Opcional) GitHub Desktop

## Puesta en marcha
powershell
cd backend
python -m venv .venv

# Activar venv:
#  - Windows PowerShell: .venv\Scripts\Activate.ps1
#  - CMD: .venv\Scripts\activate.bat
#  - Linux/Mac: source .venv/bin/activate

- pip install -r requirements.txt  # si existe, si no: pip install django
- python manage.py migrate
- python manage.py createsuperuser  # crea admin
- python manage.py runserver
- App: **http://127.0.0.1:8000/**
- Panel privado: **http://127.0.0.1:8000/panel/**
- Admin: **http://127.0.0.1:8000/admin/**

- **Grupos** creados por migración: `Admin`, `Secretario`, `Revisor`, `Vecino`.
- **Asignación de usuarios a grupos**: desde **[/admin](http://127.0.0.1:8000/admin/)** → *Users* → selecciona usuario → *Groups* → guarda.

## Flujo Git (resumen)

- **Rama principal:** `main` (protegida).
- **Ramas de trabajo:**
  - `feature/...` – nuevas funcionalidades
  - `fix/...` – correcciones
  - `chore/...` – mantenimiento (p. ej., doc, configuración)
  - `docs/...` – documentación extensa
- **Commits** con *Conventional Commits* (ver [CONTRIBUTING.md](CONTRIBUTING.md)).
- **Todo cambio va por Pull Request** hacia `main`.

## Issues y PR

- Crea un *Issue* por cada trabajo con título claro y checklist.
- Abre una rama desde el Issue (**Create a branch**) con un nombre descriptivo.
- En el PR:
  - Base: `main`, Compare: tu rama.
  - En la descripción incluye `Closes #N` (para cerrar el Issue automáticamente).
  - Pide *review* si aplica y haz *merge* cuando los checks pasen.

## Configuración por entorno

Usamos `python-dotenv` y un paquete de settings:

- `junta_ut/settings/base.py` – configuración común
- `junta_ut/settings/dev.py` – desarrollo (DEBUG=True)
- `junta_ut/settings/prod.py` – producción (DEBUG=False)

### Variables de entorno (.env)

Crea un archivo `.env` en `backend/` tomando como base `.env.example`:

- SECRET_KEY=...
- DEBUG=1
- ALLOWED_HOSTS=127.0.0.1,localhost


> **Nota**: `.env` está en `.gitignore`.

### Ejecutar en desarrollo

```bash
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  python manage.py migrate
  python manage.py runserver

