# Estructura de la Base de Datos — Sistema FACIAL PRO

## Motor y configuración general

| Parámetro       | Valor                  |
|-----------------|------------------------|
| Motor           | MySQL 8.x              |
| Base de datos   | `facial_pro_db`        |
| Charset         | `utf8mb4`              |
| Collation       | `utf8mb4_unicode_ci`   |
| Storage Engine  | InnoDB                 |

La conexión se configura mediante variables de entorno (archivo `.env`):

| Variable          | Descripción                        | Valor por defecto |
|-------------------|------------------------------------|-------------------|
| `MYSQL_HOST`      | Host del servidor MySQL            | `127.0.0.1`       |
| `MYSQL_PORT`      | Puerto                             | `3306`            |
| `MYSQL_USER`      | Usuario MySQL                      | _(requerido)_     |
| `MYSQL_PASSWORD`  | Contraseña MySQL                   | _(requerido)_     |
| `MYSQL_DATABASE`  | Nombre de la base de datos         | `facial_pro_db`   |

---

## Diagrama de relaciones

```
empleados (1) ────── (0..N) registro_acceso
     id  ◄──────── empleado_id (FK, nullable)
```

---

## Tablas

### `empleados`

Almacena el **personal autorizado** cuyo rostro es reconocido por el sistema.  
El nombre real se guarda **cifrado** (Fernet de la librería `cryptography`) para proteger datos personales.

| Columna           | Tipo                       | Restricciones                         | Descripción                                           |
|-------------------|----------------------------|---------------------------------------|-------------------------------------------------------|
| `id`              | `BIGINT UNSIGNED`          | PK · AUTO_INCREMENT · NOT NULL        | Identificador único del empleado                      |
| `nombre_cifrado`  | `TEXT`                     | NOT NULL                              | Nombre del empleado cifrado con Fernet                |
| `codigo_empleado` | `VARCHAR(64)`              | NOT NULL · UNIQUE (`uq_empleados_codigo`) | Código interno legible (ej. `EMP-001`)            |
| `ruta_imagen`     | `VARCHAR(1024)`            | NOT NULL                              | Ruta relativa a la foto de referencia del rostro      |
| `creado_en`       | `TIMESTAMP`                | NOT NULL · DEFAULT `CURRENT_TIMESTAMP`| Fecha/hora de registro del empleado                   |

**Índices:**

| Nombre                  | Tipo    | Columna          |
|-------------------------|---------|------------------|
| `PRIMARY`               | PRIMARY | `id`             |
| `uq_empleados_codigo`   | UNIQUE  | `codigo_empleado`|

**Ejemplo de fila:**

```sql
id  | nombre_cifrado       | codigo_empleado | ruta_imagen                    | creado_en
----|----------------------|-----------------|--------------------------------|--------------------
1   | gAAAAABp92Gn...==    | EMP-DEMO        | data/known_faces/demo.jpg      | 2026-01-01 00:00:00
```

---

### `registro_acceso`

Registra cada **evento de acceso** detectado por la cámara, sea exitoso, denegado o de un visitante no identificado.

| Columna        | Tipo            | Restricciones                                           | Descripción                                                                         |
|----------------|-----------------|----------------------------------------------------------|-------------------------------------------------------------------------------------|
| `id`           | `BIGINT UNSIGNED` | PK · AUTO_INCREMENT · NOT NULL                        | Identificador único del evento                                                      |
| `empleado_id`  | `BIGINT UNSIGNED` | NULL · FK → `empleados(id)` ON DELETE SET NULL ON UPDATE CASCADE | ID del empleado reconocido; `NULL` si el rostro no fue identificado  |
| `fecha_hora`   | `DATETIME(6)`   | NOT NULL · DEFAULT `CURRENT_TIMESTAMP(6)`               | Fecha y hora del evento con precisión de microsegundos                              |
| `estado`       | `VARCHAR(32)`   | NOT NULL                                                | Estado del acceso (ver valores posibles abajo)                                      |

**Valores posibles de `estado`:**

| Valor              | Significado                                                |
|--------------------|------------------------------------------------------------|
| `permitido`        | Rostro identificado como empleado autorizado               |
| `denegado`         | Rostro identificado pero acceso rechazado por el sistema   |
| `no_identificado`  | Rostro detectado pero no coincide con ningún empleado      |

**Índices:**

| Nombre                   | Tipo    | Columna        | Propósito                                   |
|--------------------------|---------|----------------|---------------------------------------------|
| `PRIMARY`                | PRIMARY | `id`           | Clave primaria                              |
| `idx_registro_empleado`  | INDEX   | `empleado_id`  | Acelerar búsquedas por empleado             |
| `idx_registro_fecha`     | INDEX   | `fecha_hora`   | Acelerar búsquedas y ordenación por fecha   |

**Restricción de integridad referencial:**

```
FOREIGN KEY (empleado_id) REFERENCES empleados(id)
  ON DELETE SET NULL   -- Si se elimina el empleado, los registros históricos se conservan con empleado_id = NULL
  ON UPDATE CASCADE    -- Si cambia el id del empleado, se actualiza automáticamente
```

**Ejemplo de filas:**

```sql
id | empleado_id | fecha_hora                  | estado
---|-------------|-----------------------------|----------------
1  | 1           | 2026-01-15 07:58:00.000000  | permitido
2  | 1           | 2026-01-15 12:31:22.500000  | permitido
3  | NULL        | 2026-01-16 09:14:00.000000  | no_identificado
4  | 1           | 2026-01-16 09:20:00.000000  | denegado
```

---

## Consultas principales del sistema

### Últimos eventos de acceso (panel lateral)

```sql
SELECT
    r.id,
    r.empleado_id,
    r.fecha_hora,
    r.estado,
    e.codigo_empleado
FROM registro_acceso r
LEFT JOIN empleados e ON e.id = r.empleado_id
ORDER BY r.fecha_hora DESC
LIMIT 30;
```

### Cargar empleados para reconocimiento facial

```sql
SELECT id, codigo_empleado, ruta_imagen
FROM empleados
ORDER BY id;
```

### Validar permiso vigente de un empleado

```sql
SELECT 1 FROM empleados WHERE id = ? LIMIT 1;
```

### Registrar un evento de acceso

```sql
INSERT INTO registro_acceso (empleado_id, estado)
VALUES (?, ?);

-- O con fecha/hora explícita:
INSERT INTO registro_acceso (empleado_id, fecha_hora, estado)
VALUES (?, ?, ?);
```

---

## Aplicar el esquema

```bash
# Desde la raíz del proyecto
mysql -h HOST -u USER -p < sql/facial_pro_db_schema.sql

# Datos de demostración (opcional)
mysql -h HOST -u USER -p < sql/seed_demo.sql
```

O pegando el contenido de los archivos `.sql` en la pestaña **SQL** de phpMyAdmin.

---

## Seguridad y privacidad

- Los **nombres** de los empleados se almacenan **cifrados** (Fernet/`cryptography`). La clave de cifrado nunca se guarda en la base de datos.
- Las credenciales de conexión se gestionan exclusivamente mediante **variables de entorno** (`.env`), nunca en el código fuente.
- Al eliminar un empleado, sus registros históricos de acceso se conservan con `empleado_id = NULL`, garantizando la trazabilidad sin violar la integridad referencial.
