
### `CONTRIBUTING.md`

# Guía de Contribución

## 1. Branches
Usa prefijos según el tipo:
- `feature/<área>-<breve-descripción>`
- `fix/<área>-<breve-descripción>`
- `chore/<tarea-mantenimiento>`
- `docs/<tópico>`

Ejemplos:
- `feature/auth-login-roles`
- `fix/core-dashboard-500`
- `docs/readme-contributing`

## 2. Commits

Tipos comunes: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`.

Ejemplos:
- `feat(auth): login/logout y protección de vistas`
- `fix(core): corrige 404 en /panel/`
- `docs: agrega guía de contribution`

## 3. Pull Requests
- Base: `main`. Compare: tu rama.
- En la descripción incluye:
  - Contexto breve.
  - Checklist de pruebas locales realizadas.
  - **Cierra el issue** con `Closes #<número>`.
- Pide revisión si aplica. Evita PR gigantes (preferible pequeños y enfocados).

## 4. Estándares de código
- Python: PEP8. Nombres claros. Funciones cortas.
- Django:
  - Config en `junta_ut/settings.py`.
  - URLs en `junta_ut/urls.py` → delegar a `core/urls.py` si crece.
  - Templates en `backend/templates/` o por app (usamos `backend/templates`).
  - Prácticas seguras: no subir credenciales ni `.env`.

## 5. Cómo correr el proyecto
```bash
cd backend
python -m venv .venv
# activar venv...
pip install -r requirements.txt  # o pip install django
python manage.py migrate
python manage.py runserver

## 6. Tests (cuando existan)
- Añade tests con **pytest** o **unittest**.
- Ejecútalos localmente antes de abrir un PR.

## 7. Convenciones de Issues
- **Título**: `[feature] ...`, `[bug] ...`, `[docs] ...`, `[chore] ...`
- **Descripción**: pasos, criterios de aceptación y, si aplica, capturas.

## 8. Seguridad
- Nunca commitear **secretos** (tokens, claves). Usa variables de entorno.
- Si detectas un problema de seguridad, repórtalo por privado al maintainer.

---

## Tips / rápidos
- Si el PR **no cierra** el issue: revisa que pusiste `Closes #N` en la **descripción** (no en un comentario).
- Si no ves la rama en GitHub Desktop: **Fetch origin** y vuelve a abrir el selector de ramas.
- Usa extensión **.md** y deja `README.md` y `CONTRIBUTING.md` en la **raíz** del repo.
