# CrimeGuard UI refresh

This update changes presentation styling only. The React pages, API calls, prediction logic, backend, model artifacts, database, and project data are retained.

## Visual direction
- Dark case-room surfaces with muted charcoal and deep blue-green panels
- Teal/cyan accents for analysis and interface focus
- Restrained evidence-red for primary actions and risk indicators
- IBM Plex Mono for small technical labels; Manrope for readable interface text
- Responsive overrides and reduced-motion support

## Run
Use the existing `run_backend.bat` and `run_frontend.bat` files as before. The theme imports `frontend/src/crime-scene-theme.css` from `App.jsx`.


## Photo-backed Crime Scene UI refresh
- Added two supplied local reference images under `frontend/public/crimeguard-assets/`.
- Applied low-opacity, dark-overlay image treatments to the login panel and dashboard hero; the photos remain local and are not fetched from an external image host.
- Added Cal Sans with Inter/Manrope fallbacks and strengthened text contrast.
- Backend, models, prediction pipeline and database were not intentionally changed in this UI refresh.
