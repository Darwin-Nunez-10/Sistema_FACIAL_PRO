# Base de Datos — Sistema FACIAL PRO

## Índice

1. [Resumen general](#1-resumen-general)
2. [Motor y configuración](#2-motor-y-configuración)
3. [Diagrama entidad-relación](#3-diagrama-entidad-relación)
4. [Tablas](#4-tablas)
   - [empleados](#41-tabla-empleados)
   - [registro_acceso](#42-tabla-registro_acceso)
5. [Relaciones entre tablas](#5-relaciones-entre-tablas)
6. [Índices y claves](#6-índices-y-claves)
7. [Seguridad y cifrado](#7-seguridad-y-cifrado)
8. [Capa de acceso desde Python](#8-capa-de-acceso-desde-python)
9. [Datos de ejemplo (seed)](#9-datos-de-ejemplo-seed)
10. [Configuración del entorno](#10-configuración-del-entorno)
11. [Cómo aplicar el esquema](#11-cómo-aplicar-el-esquema)

---

## 1. Resumen general

La base de datos **`facial_pro_db`** almacena toda la información operativa del Sistema FACIAL PRO:

| Propósito | Descripción |
|-----------|-------------|
| **Registro de empleados** | Guarda los datos del personal autorizado para acceder, junto con la ruta de su imagen de referencia facial. |
| **Auditoría de accesos** | Registra cada intento de acceso detectado por la cámara, indicando si fue permitido, denegado o si el rostro no fue identificado. |

El diseño es minimalista e intencionado: toda la lógica de reconocimiento facial ocurre en Python; la base de datos actúa como fuente de verdad de identidades y repositorio de eventos.

---

## 2. Motor y configuración

| Parámetro | Valor |
|-----------|-------|
| **Motor** | MySQL 8.x (InnoDB) |
| **Juego de caracteres** | `utf8mb4` |
| **Collation** | `utf8mb4_unicode_ci` |
| **Puerto por defecto** | `3306` |
| **Nombre de la BD** | `facial_pro_db` |

El motor InnoDB se usa en todas las tablas para garantizar soporte de **transacciones**, **claves foráneas** y recuperación ante fallos.

---

## 3. Diagrama entidad-relación

```
┌──────────────────────────────┐        ┌──────────────────────────────────────┐
│          empleados           │        │           registro_acceso             │
├──────────────────────────────┤        ├──────────────────────────────────────┤
│ PK  id          BIGINT UNSIG │◄──┐    │ PK  id          BIGINT UNSIGNED       │
│     nombre_cifrado  TEXT     │   │    │ FK  empleado_id BIGINT UNSIGNED NULL  │
│     codigo_empleado VARCHAR  │   └────│     fecha_hora  DATETIME(6)           │
│     ruta_imagen     VARCHAR  │        │     estado      VARCHAR(32)           │
│     creado_en       TIMESTAMP│        └──────────────────────────────────────┘
└──────────────────────────────┘

Cardinalidad: un empleado puede tener muchos registros de acceso (1 → N).
              Un registro puede no tener empleado asociado (NULL si el rostro
              no fue identificado).
```

---

## 4. Tablas

### 4.1 Tabla `empleados`

Almacena el **personal autorizado** por el sistema. Cada fila representa a una persona cuyo rostro ha sido enrolado.

```sql
CREATE TABLE IF NOT EXISTS empleados (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre_cifrado   TEXT            NOT NULL,
  codigo_empleado  VARCHAR(64)     NOT NULL,
  ruta_imagen      VARCHAR(1024)   NOT NULL,
  creado_en        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_empleados_codigo (codigo_empleado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

| Columna | Tipo | Nulable | Descripción |
|---------|------|---------|-------------|
| `id` | `BIGINT UNSIGNED` | NO | Clave primaria autoincremental. Identifica de forma única a cada empleado dentro del sistema. |
| `nombre_cifrado` | `TEXT` | NO | Nombre real del empleado **cifrado** (ver sección 7). Nunca se almacena en texto plano. |
| `codigo_empleado` | `VARCHAR(64)` | NO | Código alfanumérico único y legible (ej. `EMP-001`). Se usa como identificador operacional en logs y la interfaz. Tiene restricción `UNIQUE`. |
| `ruta_imagen` | `VARCHAR(1024)` | NO | Ruta relativa al proyecto de la imagen de referencia (ej. `data/known_faces/emp001.jpg`). Python la usa para cargar el encoding facial al iniciar el sistema. |
| `creado_en` | `TIMESTAMP` | NO | Fecha y hora de registro del empleado. Se asigna automáticamente con `CURRENT_TIMESTAMP`. |

---

### 4.2 Tabla `registro_acceso`

Almacena **cada evento de control de acceso** capturado por el sistema. Es la tabla de auditoría principal.

```sql
CREATE TABLE IF NOT EXISTS registro_acceso (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  empleado_id  BIGINT UNSIGNED NULL,
  fecha_hora   DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  estado       VARCHAR(32)     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_registro_empleado (empleado_id),
  KEY idx_registro_fecha    (fecha_hora),
  CONSTRAINT fk_registro_empleado
    FOREIGN KEY (empleado_id) REFERENCES empleados (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

| Columna | Tipo | Nulable | Descripción |
|---------|------|---------|-------------|
| `id` | `BIGINT UNSIGNED` | NO | Clave primaria autoincremental. |
| `empleado_id` | `BIGINT UNSIGNED` | **SÍ** | Referencia al empleado identificado. Es `NULL` cuando el rostro no coincide con ningún empleado registrado (intruso o desconocido). |
| `fecha_hora` | `DATETIME(6)` | NO | Marca de tiempo del evento con **precisión de microsegundos** (`DATETIME(6)`). Se asigna automáticamente si no se provee. |
| `estado` | `VARCHAR(32)` | NO | Resultado del evento. Valores posibles usados por el sistema: |

**Valores del campo `estado`:**

| Valor | Significado |
|-------|-------------|
| `permitido` | Rostro reconocido y empleado con permiso vigente. Se concede acceso. |
| `denegado` | Rostro reconocido, pero el empleado ya no existe o fue revocado en la BD. |
| `no_identificado` | Rostro detectado por la cámara pero no coincide con ningún empleado registrado (posible intruso). Se dispara alerta. |

---

## 5. Relaciones entre tablas

La única relación es entre `registro_acceso` y `empleados` a través de la clave foránea `fk_registro_empleado`:

```
empleados.id  ←──  registro_acceso.empleado_id
```

**Comportamiento ante cambios en `empleados`:**

| Operación en `empleados` | Efecto en `registro_acceso` |
|--------------------------|-----------------------------|
| `UPDATE` del `id` (CASCADE) | El `empleado_id` en todos sus registros se actualiza automáticamente. |
| `DELETE` de un empleado (SET NULL) | El `empleado_id` en sus registros históricos se pone en `NULL`. Los eventos quedan preservados para auditoría aunque el empleado sea eliminado. |

Este diseño garantiza la **integridad del historial**: borrar un empleado no borra sus accesos pasados.

---

## 6. Índices y claves

| Tabla | Índice | Columnas | Tipo | Propósito |
|-------|--------|----------|------|-----------|
| `empleados` | `PRIMARY` | `id` | PK | Búsqueda por ID en joins y validaciones. |
| `empleados` | `uq_empleados_codigo` | `codigo_empleado` | UNIQUE | Evita duplicados y acelera búsquedas por código. |
| `registro_acceso` | `PRIMARY` | `id` | PK | Identificador único de cada evento. |
| `registro_acceso` | `idx_registro_empleado` | `empleado_id` | INDEX | Acelera el `LEFT JOIN` con `empleados` al consultar el panel. |
| `registro_acceso` | `idx_registro_fecha` | `fecha_hora` | INDEX | Acelera el `ORDER BY fecha_hora DESC` que trae los últimos eventos al panel lateral. |

---

## 7. Seguridad y cifrado

### Nombre del empleado

El campo `nombre_cifrado` **nunca contiene texto en claro**. El nombre real se cifra antes de insertarse en la base de datos usando **Fernet** de la librería `cryptography` (cifrado simétrico AES-128-CBC con HMAC-SHA256). El texto cifrado resultante es una cadena Base64 URL-safe.

**Ventaja:** Aunque alguien acceda directamente a la base de datos, no puede leer los nombres del personal sin la clave de cifrado, que se gestiona separadamente fuera de la BD.

### Credenciales de conexión

Las credenciales de acceso a MySQL **nunca** se guardan en el código fuente. Se cargan exclusivamente desde variables de entorno definidas en un archivo `.env` (ignorado por `.gitignore`):

```
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=tu_usuario
MYSQL_PASSWORD=tu_contraseña
MYSQL_DATABASE=facial_pro_db
```

---

## 8. Capa de acceso desde Python

El módulo `src/database.py` es la única interfaz entre el sistema y la base de datos. Expone las siguientes funciones:

| Función | Descripción |
|---------|-------------|
| `get_connection()` | Abre y devuelve una conexión MySQL usando los parámetros del entorno. Devuelve `None` si faltan credenciales o hay error de conexión. |
| `fetch_recent_access_rows(limit)` | Devuelve los últimos *N* eventos de acceso (por defecto 30) con `LEFT JOIN` a `empleados`, ordenados del más reciente al más antiguo. Alimenta el panel lateral de la GUI. |
| `fetch_employees_for_recognition()` | Devuelve todos los empleados (`id`, `codigo_empleado`, `ruta_imagen`) para cargar los encodings faciales al iniciar el sistema. |
| `validate_employee_permission(empleado_id)` | Comprueba que un empleado identificado siga existiendo en la BD (permiso vigente). Devuelve `True`/`False`. |
| `insert_access_log(empleado_id, estado, fecha_hora)` | Inserta un nuevo evento en `registro_acceso`. `empleado_id` puede ser `None`. `fecha_hora` es opcional (si se omite, MySQL usa `CURRENT_TIMESTAMP(6)`). Hace commit o rollback según el resultado. |

Todas las funciones abren y cierran su propia conexión, capturan excepciones `MySQLError` y exponen el último error mediante `db_last_error()` para mostrarlo en la barra de estado de la GUI.

---

## 9. Datos de ejemplo (seed)

El archivo `sql/seed_demo.sql` inserta datos de prueba mínimos:

- **1 empleado** con `codigo_empleado = 'EMP-DEMO'` e imagen de referencia en `data/known_faces/demo.jpg`.
- **6 eventos de acceso** para ese empleado, cubriendo los tres estados posibles:
  - 3 eventos `permitido`
  - 1 evento `denegado`
  - 2 eventos `no_identificado` (con `empleado_id = NULL`)

Estos datos permiten probar el panel de registros sin necesidad de hacer pasar una cara real frente a la cámara.

---

## 10. Configuración del entorno

Variables de entorno relevantes para la base de datos (archivo `.env`):

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `MYSQL_HOST` | `127.0.0.1` | Host del servidor MySQL. `localhost` se normaliza a `127.0.0.1` para evitar problemas IPv6 en Linux con Docker. |
| `MYSQL_PORT` | `3306` | Puerto TCP de MySQL. |
| `MYSQL_USER` | *(requerido)* | Usuario MySQL con permisos sobre `facial_pro_db`. |
| `MYSQL_PASSWORD` | *(requerido)* | Contraseña del usuario MySQL. |
| `MYSQL_DATABASE` | `facial_pro_db` | Nombre de la base de datos. |

**Permisos mínimos recomendados para el usuario de la aplicación:**

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON facial_pro_db.* TO 'app_user'@'%';
FLUSH PRIVILEGES;
```

Para desarrollo local se puede usar `GRANT ALL PRIVILEGES` por comodidad, pero en producción se deben otorgar solo los permisos necesarios.

---

## 11. Cómo aplicar el esquema

### Opción A — Cliente MySQL desde terminal

```bash
mysql -h 127.0.0.1 -u root -p < sql/facial_pro_db_schema.sql
```

### Opción B — phpMyAdmin

1. Abrir phpMyAdmin en el navegador.
2. Ir a la pestaña **SQL**.
3. Pegar el contenido de `sql/facial_pro_db_schema.sql` y ejecutar.

### Opción C — Docker Compose

El archivo `docker-compose.yml` del proyecto puede levantar un contenedor MySQL listo para usar. Revisar ese archivo para los detalles de variables y puertos expuestos.

### Cargar datos de prueba (opcional)

```bash
mysql -h 127.0.0.1 -u root -p < sql/seed_demo.sql
```

> **Nota:** Antes de ejecutar el seed, asegúrese de colocar una imagen con un rostro claro en `data/known_faces/demo.jpg`.
