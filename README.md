# Sistema FACIAL PRO

Aplicacion de escritorio en Python para control de ingreso con reconocimiento facial, base de datos MySQL y medidas de privacidad (cifrado).

## Estructura del proyecto

```
Sistema_FACIAL_PRO/
??? data/
?   ??? known_faces/
?   ??? unknown_faces/
??? sql/
?   ??? facial_pro_db_schema.sql
??? src/
?   ??? gui.py
?   ??? database.py
?   ??? detector.py
?   ??? notifications.py
?   ??? utils.py
??? main.py
??? config.py
??? docker-compose.yml
??? requirements.txt
??? README.md
```

## Requisitos

- Python 3.10 o superior (recomendado)
- Servidor MySQL 8 (local o Docker)
- Linux: paquete **tkinter** (`sudo apt install python3-tk` en Debian/Ubuntu)
- **face_recognition** compila **dlib**; puede necesitar `build-essential`, `cmake` y librerias de desarrollo (ver documentacion de `dlib` / `face_recognition`)

## Librerias (lista del profesor y uso)

| Libreria | Punto 1 (esta entrega) | Nota |
|----------|------------------------|------|
| opencv-python | Si | Video y dibujo de rectangulos |
| face_recognition | Si | Deteccion de rostros (bounding boxes) |
| mysql-connector-python | Si | Panel de ultimos registros |
| tkinter o PyQt5 | Si | Aqui se usa **tkinter** (incluido en Python; en Linux instalar `python3-tk`) |
| Pillow | Si (soporte) | Para mostrar fotogramas en Tkinter (`ImageTk`) |
| python-dotenv | Si (soporte) | Carga `.env` al ejecutar `main.py` |
| cryptography | No aun | Cifrado de datos personales (otros modulos) |
| smtplib | No aun | Correo (biblioteca estandar; sin `pip`) |

## Instalacion

```bash
cd Sistema_FACIAL_PRO
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

## Configuracion

1. Copie `.env.example` a `.env` y ponga **sus** credenciales locales (`MYSQL_*`, etc.).
2. Nombre de base por defecto del proyecto: **`facial_pro_db`** (`MYSQL_DATABASE`).
3. **Docker Compose y Python:** si en `.env` usa `$$` para un `$` en la clave (solo interpretacion de Compose), `python-dotenv` puede cargar la cadena tal cual y la app no conectaria. En desarrollo use clave **sin caracter `$`** o exporte `MYSQL_PASSWORD` en la terminal con el valor exacto antes de `python main.py`.

## Base de datos `facial_pro_db`

Script versionado: [`sql/facial_pro_db_schema.sql`](sql/facial_pro_db_schema.sql).

- **empleados**: `id`, `nombre_cifrado`, `codigo_empleado` (unico), `ruta_imagen`, `creado_en`.
- **registro_acceso**: `id`, `empleado_id` (FK, nullable), `fecha_hora` (DATETIME(6)), `estado`.

### Aplicar el esquema manualmente

```bash
mysql -h 127.0.0.1 -P 3306 -u TU_USUARIO -p < sql/facial_pro_db_schema.sql
```

O importar / pegar el SQL en phpMyAdmin.

### Docker Compose (MySQL + phpMyAdmin)

En el **primer** arranque con volumen de datos nuevo, el contenedor ejecuta el mismo script desde `docker-entrypoint-initdb.d`. Si ya tenia datos el volumen `mysql_data`, el script **no** se vuelve a ejecutar: aplique `sql/facial_pro_db_schema.sql` a mano o borre el volumen sabiendo que perdera datos.

```bash
docker compose up -d
```

phpMyAdmin queda en `http://127.0.0.1:8090` por defecto. Si el puerto esta ocupado, en `.env` defina otro, por ejemplo `PMA_HTTP_PORT=8091`. No use `PMA_PORT` para el puerto web: en la imagen oficial es el de conexion a MySQL.

## Ejecucion

```bash
python main.py
```

## Publicar en GitHub

Con [GitHub CLI](https://cli.github.com/) (`gh`):

```bash
gh repo create Sistema_FACIAL_PRO --public --source=. --remote=origin --push
```

Si el repo ya existe:

```bash
git remote add origin https://github.com/TU_USUARIO/Sistema_FACIAL_PRO.git
git push -u origin main
```

## Licencia

Uso academico / segun indique el autor del proyecto.
