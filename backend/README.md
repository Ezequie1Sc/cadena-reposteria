# Entrega comercial actual

Backend existente ampliado con ventas, pagos manuales, pedidos de clientes, tickets, solicitudes de factura y reportes.

- [Informe de implementación](IMPLEMENTATION_REPORT.md)
- [Cobertura del alcance](PROJECT_SCOPE_COVERAGE.md)
- [Resultados de pruebas](TEST_RESULTS.md)
- [Migraciones](DATABASE_MIGRATION_GUIDE.md)
- [Integración Angular/Flutter](FRONTEND_INTEGRATION.md)
- [Windows](WINDOWS_SETUP.md)
- [Reglas comerciales](COMMERCIAL_RULES.md)
- [Matriz de endpoints](ENDPOINT_AUTHORIZATION.md)

Los documentos y resultados bajo `docs/security/` se conservan como historial de la auditoría previa; no representan el recuento actual de endpoints y pruebas. Esta entrega requiere la nueva migración antes de usar las operaciones comerciales. No se ejecutaron cambios en producción.

---

# Cadena de Repostería — backend corregido

Corrección del backend existente; no se reconstruyó el proyecto ni se desarrollaron módulos comerciales nuevos. Las 56 operaciones HTTP únicas se conservan. La revisión de seguridad y los cambios de compatibilidad están documentados.

Empieza por [las instrucciones de Windows](docs/security/WINDOWS.md). Configura `.env` a partir de `.env.example`, genera una clave JWT aleatoria y conserva tu conexión autorizada hasta validar por separado la propuesta de privilegios.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

La suite portable no usa credenciales de producción; las cuatro pruebas PostgreSQL necesitan activación y una base local desechable. Consulta los comandos completos antes de ejecutarlas.

Documentación incluida:

- [Informe de auditoría](docs/security/AUDITORIA.md).
- [Matriz completa de endpoints](docs/security/MATRIZ_ENDPOINTS.md) y [CSV](docs/security/MATRIZ_ENDPOINTS.csv).
- [Resultados reales](docs/security/RESULTADOS_PRUEBAS.md), con salida Pytest/JUnit y evidencia de compatibilidad.
- [Resumen de modificaciones](docs/security/CAMBIOS.md) y manifiesto de archivos.
- [Propuesta PostgreSQL/Supabase](docs/security/SUPABASE.md); los SQL de `scripts/sql/` no se aplicaron a producción.
- [Propuesta de Pull Request](docs/security/PULL_REQUEST.md).

No ejecutes el esquema SQL de referencia ni migraciones automáticamente contra Supabase. No hay credenciales reales, entorno virtual ni cachés dentro de esta entrega.
