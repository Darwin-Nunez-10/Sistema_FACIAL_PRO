# Sistema FACIAL PRO

Aplicación de escritorio en Python para control de ingreso con reconocimiento facial, base de datos MySQL y medidas de privacidad (cifrado).

## Estructura del proyecto

```
Sistema_FACIAL_PRO/
??? data/
?   ??? known_faces/      # Fotos de empleados autorizados
?   ??? unknown_faces/    # Capturas de auditoría (alertas)
??? src/
?   ??? gui.py            # Interfaz gráfica
?   ??? database.py       # MySQL
?   ??? detector.py       # Reconocimiento y cifrado
?   ??? notifications.py  # Email y alertas
?   ??? utils.py
??? main.py
??? config.py
??? requirements.txt
??? README.md
```

## Requisitos

- Python 3.10 o superior (recomendado)
- Servidor MySQL (para las tablas de empleados y registro de accesos)

## Instalación

```bash
cd Sistema_FACIAL_PRO
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

## Configuración

1. Copie `.env.example` a `.env` y complete los valores (el archivo `.env` no se sube al repositorio).
2. O exporte las mismas variables en su shell antes de ejecutar la aplicación.

Variables principales: `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, y para correo `SMTP_*` y `SECURITY_EMAIL`.

## MySQL (esquema orientativo)

- **empleados**: id, nombre (cifrado), código de empleado, ruta de imagen.
- **registro_acceso**: id, empleado_id, fecha_hora, estado del acceso.

El script SQL concreto se añadirá al implementar el módulo `database.py`.

## Ejecución

```bash
python main.py
```

La interfaz y el flujo completo se irán completando por módulos.

## Licencia

Uso académico / según indique el autor del proyecto.
