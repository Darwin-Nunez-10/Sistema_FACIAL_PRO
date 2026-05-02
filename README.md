# Sistema FACIAL PRO

Aplicacion de escritorio en Python para control de ingreso con reconocimiento facial, base de datos MySQL y medidas de privacidad (cifrado).

## Estructura del proyecto

```
Sistema_FACIAL_PRO/
??? data/
?   ??? known_faces/      # Fotos de empleados autorizados
?   ??? unknown_faces/    # Capturas de auditoria (alertas)
??? src/
?   ??? gui.py            # Interfaz grafica
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

## Instalacion

```bash
cd Sistema_FACIAL_PRO
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

## Configuracion

1. Copie `.env.example` a `.env` y complete los valores (el archivo `.env` no se sube al repositorio).
2. O exporte las mismas variables en su shell antes de ejecutar la aplicacion.

Variables principales: `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, y para correo `SMTP_*` y `SECURITY_EMAIL`.

## MySQL (esquema orientativo)

- **empleados**: id, nombre (cifrado), codigo de empleado, ruta de imagen.
- **registro_acceso**: id, empleado_id, fecha_hora, estado del acceso.

El script SQL concreto se anadira al implementar el modulo `database.py`.

## Ejecucion

```bash
python main.py
```

La interfaz y el flujo completo se iran completando por modulos.

## Publicar en GitHub

Con [GitHub CLI](https://cli.github.com/) (`gh`), desde la raiz del proyecto y con sesion valida (`gh auth login`):

```bash
gh repo create Sistema_FACIAL_PRO --public --source=. --remote=origin --push
```

Ajuste `--public` a `--private` si lo necesita. Si el repositorio ya existe en GitHub:

```bash
git remote add origin https://github.com/TU_USUARIO/Sistema_FACIAL_PRO.git
git push -u origin main
```

(Con SSH: `git@github.com:TU_USUARIO/Sistema_FACIAL_PRO.git`.)

## Licencia

Uso academico / segun indique el autor del proyecto.
