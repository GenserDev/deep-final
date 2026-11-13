from servicio.bases import Bases, es_solo_lectura, traducir

bases = Bases()


def test_tamano_de_las_tablas_igual_a_mysql():
    assert bases.ejecutar("veterinaria", "SELECT COUNT(*) FROM vet_cons")["filas"] == [(420,)]
    assert bases.ejecutar("airline", "SELECT COUNT(*) FROM bookings")["filas"] == [(700,)]


def test_funciones_de_fecha_de_mysql():
    resultado = bases.ejecutar("veterinaria", "SELECT YEAR(cons_fec), MONTH(cons_fec) FROM vet_cons LIMIT 1")
    anio, mes = resultado["filas"][0]
    assert 2023 <= anio <= 2025 and 1 <= mes <= 12


def test_bloquea_escritura():
    for sql in ["DROP TABLE vet_med", "DELETE FROM vet_med", "SELECT 1; DROP TABLE vet_med", "UPDATE vet_med SET med_precio = 0"]:
        assert not es_solo_lectura(sql)
        assert not bases.ejecutar("veterinaria", sql)["ok"]
    assert bases.ejecutar("veterinaria", "SELECT COUNT(*) FROM vet_med")["filas"] == [(25,)]


def test_acepta_with_y_ventanas():
    sql = "WITH r AS (SELECT masc_esp, RANK() OVER (PARTITION BY masc_esp ORDER BY masc_peso DESC) AS pos FROM vet_masc) SELECT * FROM r WHERE pos = 1"
    assert es_solo_lectura(sql)
    assert bases.ejecutar("veterinaria", sql)["ok"]


def test_error_de_columna_inexistente():
    resultado = bases.ejecutar("veterinaria", "SELECT nada FROM vet_masc")
    assert not resultado["ok"] and "nada" in resultado["error"]


def test_traduce_comillas_de_mysql():
    assert '"vet_masc"' in traducir("SELECT * FROM `vet_masc`")
