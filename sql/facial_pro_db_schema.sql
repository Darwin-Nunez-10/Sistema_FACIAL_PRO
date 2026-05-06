-- Esquema facial_pro_db — Sistema FACIAL PRO
-- MySQL 8.x
--
-- Aplicar:
--   mysql -h HOST -u USER -p < sql/facial_pro_db_schema.sql
--
-- Permisos (ajustar usuario/clave):
--   GRANT ALL PRIVILEGES ON facial_pro_db.* TO 'tu_usuario'@'%';
--   FLUSH PRIVILEGES;

CREATE DATABASE IF NOT EXISTS facial_pro_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE facial_pro_db;

-- Personal autorizado. nombre_cifrado: texto cifrado con Fernet.
CREATE TABLE IF NOT EXISTS empleados (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre_cifrado  TEXT            NOT NULL,
  codigo_empleado VARCHAR(64)     NOT NULL,
  ruta_imagen     VARCHAR(1024)   NOT NULL,
  creado_en       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_empleados_codigo (codigo_empleado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Registro de eventos de acceso.
-- empleado_id NULL si el rostro no corresponde a ningun empleado.
CREATE TABLE IF NOT EXISTS registro_acceso (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  empleado_id  BIGINT UNSIGNED NULL,
  fecha_hora   DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  estado       VARCHAR(32)     NOT NULL COMMENT 'permitido | no_identificado',
  PRIMARY KEY (id),
  KEY idx_registro_empleado (empleado_id),
  KEY idx_registro_fecha    (fecha_hora),
  CONSTRAINT fk_registro_empleado
    FOREIGN KEY (empleado_id) REFERENCES empleados (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
