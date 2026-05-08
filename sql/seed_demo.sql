-- Datos de prueba (ejecutar a mano en phpMyAdmin o mysql client).
-- Coloque antes una foto con un rostro claro en: data/known_faces/demo.jpg
-- (ruta relativa al proyecto).

USE facial_pro_db;

INSERT INTO empleados (nombre_cifrado, codigo_empleado, ruta_imagen)
VALUES (
  'gAAAAABp92GnecLvh0pS8njjQGHPJjSxtm-P0931c5zdYw3PIv6R7yDdzhAqmfn3yvV0vN5sp7rKGtkgF5zhbk9thnKoI2KFwQ==',
  'EMP-DEMO',
  'data/known_faces/demo.jpg'
);

-- Eventos de acceso de ejemplo (empleado_id enlaza al demo; NULL = visitante no reconocido).
INSERT INTO registro_acceso (empleado_id, fecha_hora, estado)
VALUES
  ((SELECT id FROM empleados WHERE codigo_empleado = 'EMP-DEMO' LIMIT 1), '2026-01-15 07:58:00.000000', 'permitido'),
  ((SELECT id FROM empleados WHERE codigo_empleado = 'EMP-DEMO' LIMIT 1), '2026-01-15 12:31:22.500000', 'permitido'),
  ((SELECT id FROM empleados WHERE codigo_empleado = 'EMP-DEMO' LIMIT 1), '2026-01-15 18:05:10.123456', 'permitido'),
  (NULL, '2026-01-16 09:14:00.000000', 'no_identificado'),
  ((SELECT id FROM empleados WHERE codigo_empleado = 'EMP-DEMO' LIMIT 1), '2026-01-16 09:20:00.000000', 'denegado'),
  (NULL, '2026-01-16 17:45:33.789012', 'no_identificado');
