from servicio.bases import esquema_texto
from servicio.modelo import armar_mensajes, compactar_esquema, limpiar_sql


def test_compactar_quita_lo_que_no_ayuda():
    compacto = compactar_esquema(esquema_texto("veterinaria"))
    assert "ENGINE" not in compacto and "AUTO_INCREMENT" not in compacto and "`" not in compacto
    assert "FOREIGN KEY (masc_id) REFERENCES vet_masc(masc_id)" in compacto
    assert "COMMENT='mascotas atendidas'" in compacto


def test_limpiar_sql():
    assert limpiar_sql("```sql\nSELECT 1;\n```") == "SELECT 1;"
    assert limpiar_sql("Aquí está: SELECT a FROM b; SELECT c") == "SELECT a FROM b;"


def test_mensajes_de_correccion():
    mensajes = armar_mensajes("CREATE TABLE t (a int);", "pregunta", "SELECT b FROM t", "Unknown column b")
    assert mensajes[0]["role"] == "system"
    assert "Unknown column b" in mensajes[1]["content"]
